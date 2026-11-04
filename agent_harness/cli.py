import argparse
import getpass
import json
import os
import shutil
import sys
import uuid
import webbrowser
from pathlib import Path

from . import __version__
from .config import Config
from .provider import NineRouterClient
from .runtime import Runtime
from .store import Store


def _config(workspace=None): return Config.from_env(workspace)


def doctor(workspace=None):
    try:
        config=_config(workspace)
    except ValueError as exc:
        print(f"Configuration incomplete: {exc}")
        print("Set AGENT_HARNESS_BASE_URL, AGENT_HARNESS_MODEL and AGENT_HARNESS_API_KEY.")
        return 2
    print(f"Agent Harness {__version__}")
    print(f"Workspace: {config.workspace}")
    print(f"Data: {config.data_dir}")
    print(f"Router: {config.base_url}")
    print(f"Model: {config.model}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Git: {shutil.which('git') or 'not installed'}")
    print("Command execution: " + (", ".join(config.allow_commands) if config.allow_commands else "disabled"))
    client=NineRouterClient(config.base_url,config.api_key,config.timeout,config.retries)
    try:
        client.chat(config.model,[{"role":"user","content":"Reply with OK."}],max_tokens=8)
    except Exception as exc:
        print(f"9Router check failed: {exc}")
        print("Check the router URL, dashboard API key, configured model, and that 9Router is running.")
        return 1
    print("9Router Chat Completions check: OK")
    return 0


def configure():
    path=Path(os.getenv("AGENT_HARNESS_HOME",Path.home()/".haness-9router"))
    path.mkdir(parents=True,exist_ok=True)
    cfg=path/"config.env"
    if cfg.exists():
        print(f"Configuration already exists: {cfg}; leaving it unchanged.")
        return 0
    base=input("9Router Base URL [http://localhost:20128/v1]: ").strip() or "http://localhost:20128/v1"
    model=input("Model ID from your 9Router configuration: ").strip()
    key=getpass.getpass("API key (hidden input): ").strip()
    if not model or not key:
        print("Model ID and API key are required; no configuration saved.")
        return 2
    cfg.write_text(f"AGENT_HARNESS_BASE_URL={base}\nAGENT_HARNESS_MODEL={model}\nAGENT_HARNESS_API_KEY={key}\n",encoding="utf-8")
    try: cfg.chmod(0o600)
    except OSError: pass
    print(f"Saved user configuration to {cfg}. It is outside the repository.")
    print("Load this file as environment variables before running the launcher (see README).")
    return 0


def load_user_config():
    path=Path(os.getenv("AGENT_HARNESS_HOME",Path.home()/".haness-9router"))/"config.env"
    if not path.exists(): return
    for line in path.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        key,value=line.split("=",1)
        if key.startswith("AGENT_HARNESS_") and key not in os.environ:
            os.environ[key]=value


def main(argv=None):
    parser=argparse.ArgumentParser(prog="agent-harness",description="Coding agent harness for 9Router")
    parser.add_argument("--workspace",default=None,help="Existing repository directory")
    sub=parser.add_subparsers(dest="action",required=True)
    sub.add_parser("configure")
    sub.add_parser("doctor")
    sub.add_parser("status")
    web=sub.add_parser("web",help="Start the loopback-only local browser interface")
    web.add_argument("--host",choices=("127.0.0.1","localhost"),default="127.0.0.1")
    web.add_argument("--port",type=int,default=8765)
    web.add_argument("--no-browser",action="store_true",help="Do not open a browser window")
    run=sub.add_parser("run"); run.add_argument("request",nargs="+")
    resume=sub.add_parser("resume"); resume.add_argument("task_id",nargs="?")
    stop=sub.add_parser("stop"); stop.add_argument("task_id")
    sub.add_parser("update")
    export=sub.add_parser("export"); export.add_argument("destination")
    imp=sub.add_parser("import"); imp.add_argument("source")
    args=parser.parse_args(argv)
    if args.action=="configure": return configure()
    load_user_config()
    if args.action=="doctor": return doctor(args.workspace)
    config=_config(args.workspace)
    store=Store(config.data_dir/"state.sqlite3")
    if args.action=="status":
        for task in store.all_tasks(): print(f"{task['id']}  {task['status']}  {task['model'] or '-'}  {task['request'][:100]}")
        store.close()
        return 0
    runtime=Runtime(config,NineRouterClient(config.base_url,config.api_key,config.timeout,config.retries),store)
    if args.action=="web":
        from .webserver import LocalWebServer
        if not 0 <= args.port <= 65535:
            parser.error("--port must be between 0 and 65535")
        try:
            server=LocalWebServer(config,store,runtime,args.host,args.port)
        except OSError as exc:
            store.close()
            print(f"Could not start local web UI: {exc}",file=sys.stderr)
            print("Choose another port with --port, or stop the process using this port.",file=sys.stderr)
            return 1
        url=f"http://127.0.0.1:{server.server_port}/"
        print(f"Haness web UI: {url}",flush=True)
        print("Local only. Press Ctrl+C to stop; task history stays in the existing data directory.",flush=True)
        if not args.no_browser:
            try: webbrowser.open(url)
            except Exception: print(f"Open this URL in your browser: {url}",file=sys.stderr)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Stopping Haness web UI.")
        finally:
            server.stop_worker()
            server.server_close()
            store.close()
        return 0
    if args.action=="run":
        task,session=runtime.new_task(" ".join(args.request)); print(f"Task {task} | Session {session}")
        try: print(runtime.run(task))
        except Exception as exc:
            print(f"Task paused/failed: {exc}",file=sys.stderr)
            store.close()
            return 1
        store.close()
        return 0
    if args.action=="resume":
        task_id=args.task_id
        if not task_id:
            tasks=store.active_tasks()
            if len(tasks)!=1:
                print("Pass a task ID (there must be exactly one active task).",file=sys.stderr)
                store.close()
                return 2
            task_id=tasks[0]["id"]
        try: print(runtime.run(task_id,resume=True))
        except Exception as exc:
            print(f"Resume paused/failed: {exc}",file=sys.stderr)
            store.close()
            return 1
        store.close()
        return 0
    if args.action=="stop":
        runtime.stop(args.task_id)
        print("Stop recorded; active synchronous model calls finish or hit timeout first.")
        store.close()
        return 0
    if args.action=="update":
        print("No release URL is configured. For a local checkout, update with your normal Git workflow; user data is separate.")
        store.close()
        return 0
    if args.action in ("export","import"):
        source=Path(args.destination if args.action=="export" else args.source)
        if args.action=="export":
            source.parent.mkdir(parents=True,exist_ok=True)
            payload={"format":"agent-harness-export-v1","tasks":[]}
            for task in store.all_tasks():
                payload["tasks"].append({"name":task.get("name"),"request":task["request"],"status":task["status"],"model":task["model"],
                    "events":[{"kind":e["kind"],"payload":e["payload"]} for e in store.events(task["id"])]})
            source.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
            print(f"Exported task history (without machine workspace paths or credentials) to {source}")
        else:
            if not source.is_file():
                print("Import source does not exist",file=sys.stderr)
                store.close()
                return 2
            try: payload=json.loads(source.read_text(encoding="utf-8"))
            except (OSError,json.JSONDecodeError):
                print("Import file is unreadable JSON",file=sys.stderr)
                store.close()
                return 2
            if payload.get("format")!="agent-harness-export-v1":
                print("Unsupported export format",file=sys.stderr)
                store.close()
                return 2
            for task in payload.get("tasks",[]):
                tid,_=store.create_task(config.workspace,task["request"],task.get("model"),task.get("name"))
                status=task.get("status")
                if status not in {"queued","running","paused","completed","failed"}: status="paused"
                # In-flight work must resume explicitly; imported tasks never auto-run.
                if status in {"queued","running"}: status="paused"
                store.set_status(tid,status,task.get("model"))
                for event in task.get("events",[]):
                    store.event(tid,event["kind"],event.get("payload",{}))
                identity=next((event.get("payload") for event in task.get("events",[]) if event.get("kind")=="workspace_identity"),None)
                store.event(tid,"import_marker",{"identity":identity,"new_workspace":config.workspace.name})
            print(f"Imported task history into current workspace: {config.workspace}")
        store.close()
        return 0
    store.close()
    return 2


if __name__=="__main__": raise SystemExit(main())
