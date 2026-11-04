import difflib
import fnmatch
import json
import os
import shlex
import subprocess
import time
from pathlib import Path

from .policy import PermissionDenied, WorkspacePolicy


def schema(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}}


class Tools:
    def __init__(self, workspace, allow_commands=(), command_timeout=60, output_limit=20000):
        self.policy = WorkspacePolicy(workspace)
        self.allow_commands = tuple(allow_commands)
        self.command_timeout = command_timeout
        self.output_limit = output_limit
        self.specs = [
            schema("list_files", "List relative paths in the workspace, optionally matching a glob.", {"pattern":{"type":"string"}}, []),
            schema("search_text", "Search UTF-8 text files for a literal string; output is capped.", {"query":{"type":"string"},"pattern":{"type":"string"}}, ["query"]),
            schema("read_file", "Read a UTF-8 file, optionally from a 1-based line and for a bounded number of lines.", {"path":{"type":"string"},"start_line":{"type":"integer"},"max_lines":{"type":"integer"}}, ["path"]),
            schema("write_file", "Write or replace a UTF-8 workspace file. The response includes a diff preview.", {"path":{"type":"string"},"content":{"type":"string"}}, ["path","content"]),
            schema("apply_patch", "Apply one exact text replacement in a UTF-8 workspace file. The search text must occur exactly once.", {"path":{"type":"string"},"search":{"type":"string"},"replace":{"type":"string"}}, ["path","search","replace"]),
            schema("git_status", "Show concise git status for the workspace.", {}, []),
            schema("git_diff", "Show git diff for the workspace, capped.", {}, []),
            schema("run_command", "Run a command only when its first executable token matches AGENT_HARNESS_ALLOW_COMMANDS. Timeout and output are limited.", {"command":{"type":"string"}}, ["command"]),
        ]

    def call(self, name, arguments):
        methods = {"list_files":self.list_files,"search_text":self.search_text,"read_file":self.read_file,
                   "write_file":self.write_file,"apply_patch":self.apply_patch,"git_status":self.git_status,"git_diff":self.git_diff,"run_command":self.run_command}
        if name not in methods: raise ValueError("Unknown tool")
        return methods[name](**arguments)

    def list_files(self, pattern="**/*"):
        paths=[]
        for p in self.policy.root.rglob("*"):
            rel=p.relative_to(self.policy.root).as_posix()
            try: self.policy.resolve(rel)
            except PermissionDenied: continue
            matches=pattern in ("*","**/*") or fnmatch.fnmatch(rel,pattern) or Path(rel).match(pattern)
            if p.is_file() and not any(part in {".git",".venv","node_modules","__pycache__"} for part in p.parts) and matches: paths.append(rel)
            if len(paths)>=2000: break
        return "\n".join(paths)

    def search_text(self, query, pattern="**/*"):
        found=[]
        for rel in self.list_files(pattern).splitlines():
            try:
                path=self.policy.resolve(rel)
                if path.stat().st_size>1_000_000: continue
                for n,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
                    if query in line: found.append(f"{rel}:{n}:{line[:500]}")
                    if len(found)>=200: return "\n".join(found)[:self.output_limit]
            except (UnicodeError,OSError): continue
        return "\n".join(found)[:self.output_limit]

    def read_file(self, path, start_line=1, max_lines=300):
        if start_line<1 or not 1<=max_lines<=1000: raise ValueError("Invalid line range")
        target=self.policy.resolve(path)
        lines=target.read_text(encoding="utf-8").splitlines()
        return "\n".join(f"{i}: {line}" for i,line in enumerate(lines[start_line-1:start_line-1+max_lines],start_line))[:self.output_limit]

    def write_file(self, path, content):
        target=self.policy.resolve(path,allow_missing=True)
        if target.is_dir(): raise ValueError("Target is a directory")
        old=target.read_text(encoding="utf-8").splitlines(keepends=True) if target.exists() else []
        target.parent.mkdir(parents=True,exist_ok=True)
        # Recheck after parent creation to catch symlink changes.
        target=self.policy.resolve(path,allow_missing=True)
        target.write_text(content,encoding="utf-8")
        diff="".join(difflib.unified_diff(old,content.splitlines(keepends=True),fromfile=path,tofile=path))
        return ("Written. Diff preview:\n"+diff)[:self.output_limit]

    def apply_patch(self, path, search, replace):
        if not search: raise ValueError("Patch search text cannot be empty")
        target=self.policy.resolve(path)
        original=target.read_text(encoding="utf-8")
        if original.count(search)!=1: raise ValueError("Patch must match exactly one occurrence")
        updated=original.replace(search,replace,1)
        return self.write_file(path,updated)

    def git_status(self): return self._git(["status","--short","--branch"])
    def git_diff(self): return self._git(["diff","--"])
    def _git(self,args):
        try:
            result=self._run(["git",*args])
            if result.startswith("exit_code=") and result.splitlines()[0] != "exit_code=0":
                return "Git status unavailable (workspace may not be a Git repository)."
            return result
        except (FileNotFoundError,subprocess.CalledProcessError,PermissionError): return "Git status unavailable (workspace may not be a Git repository)."

    def run_command(self, command):
        argv=shlex.split(command, posix=True)
        if not argv or argv[0] not in self.allow_commands:
            raise PermissionDenied("Command is disabled; configure its executable in AGENT_HARNESS_ALLOW_COMMANDS")
        return self._run(argv)

    def _run(self, argv):
        try:
            environment=os.environ.copy()
            environment.pop("AGENT_HARNESS_API_KEY",None)
            result=subprocess.run(argv,cwd=self.policy.root,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                text=True,encoding="utf-8",errors="replace",timeout=self.command_timeout,check=False,shell=False,env=environment)
        except subprocess.TimeoutExpired as exc:
            output=exc.stdout or b""
            if isinstance(output,bytes): output=output.decode("utf-8","replace")
            return f"Timed out after {self.command_timeout}s.\n{output[-self.output_limit:]}"
        return f"exit_code={result.returncode}\n{result.stdout[-self.output_limit:]}"
