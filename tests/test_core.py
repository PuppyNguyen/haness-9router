import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from agent_harness.config import Config
from agent_harness.policy import WorkspacePolicy, PermissionDenied
from agent_harness.provider import NineRouterClient, ProviderError
from agent_harness.runtime import Runtime
from agent_harness.store import Store
from agent_harness.cli import main


class ConfigTests(unittest.TestCase):
    def test_requires_model_and_reads_secret_without_echoing(self):
        with patch.dict(os.environ, {"AGENT_HARNESS_API_KEY": "do-not-print"}, clear=True):
            with self.assertRaisesRegex(ValueError, "AGENT_HARNESS_MODEL"):
                Config.from_env()

    def test_reads_configured_openai_compatible_fields(self):
        with patch.dict(os.environ, {
            "AGENT_HARNESS_BASE_URL": "http://127.0.0.1:20128/v1/",
            "AGENT_HARNESS_API_KEY": "secret", "AGENT_HARNESS_MODEL": "local/model",
            "AGENT_HARNESS_MAX_REQUESTS": "7",
        }, clear=True):
            config = Config.from_env()
        self.assertEqual(config.base_url, "http://127.0.0.1:20128/v1")
        self.assertEqual(config.model, "local/model")
        self.assertEqual(config.max_requests, 7)


class PolicyTests(unittest.TestCase):
    def test_rejects_parent_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            root.mkdir()
            outside = Path(temp) / "private.txt"
            outside.write_text("secret")
            (root / "escape").symlink_to(outside)
            policy = WorkspacePolicy(root)
            with self.assertRaises(PermissionDenied):
                policy.resolve("../private.txt")
            with self.assertRaises(PermissionDenied):
                policy.resolve("escape")


class StoreMigrationTests(unittest.TestCase):
    def test_adds_name_to_existing_task_table_and_backfills_request_title(self):
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "state.sqlite3"
            connection = sqlite3.connect(db_path)
            connection.execute("CREATE TABLE tasks(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, workspace TEXT NOT NULL, request TEXT NOT NULL, status TEXT NOT NULL, model TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            connection.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?)", ("id", "session", temp, "Old task request", "paused", "m", "now", "now"))
            connection.commit()
            connection.close()
            store = Store(db_path)
            self.assertEqual(store.task("id")["name"], "Old task request")
            new_id, _ = store.create_task(temp, "Do something", "m", "Named task")
            self.assertEqual(store.task(new_id)["name"], "Named task")
            store.close()

    def test_selected_model_and_router_connection_settings_survive_store_reopen(self):
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "state.sqlite3"
            store = Store(db_path)
            task_id, _ = store.create_task(temp, "Task", "model-a")
            store.set_selected_model_id("cx/model-b")
            self.assertEqual(store.selected_model_id(), "cx/model-b")
            store.set_setting("web.router_base_url", "https://router.example/v1")
            store.set_setting("web.router_disconnected", "true")
            self.assertEqual(store.task(task_id)["model"], "model-a")
            store.close()
            reopened = Store(db_path)
            self.assertEqual(reopened.selected_model_id(), "cx/model-b")
            self.assertEqual(reopened.setting("web.router_base_url"), "https://router.example/v1")
            self.assertEqual(reopened.setting("web.router_disconnected"), "true")
            reopened.close()


class ProviderTests(unittest.TestCase):
    def test_lists_models_from_authenticated_endpoint_with_bounded_response(self):
        seen = {}
        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["auth"] = request.get_header("Authorization")
            seen["method"] = request.get_method()
            class Response:
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self, size=-1):
                    seen["size"] = size
                    return b'{"data":[{"id":"model-a"},{"id":"model-b"},{"id":"model-a"}]}'
            return Response()
        client = NineRouterClient("http://router/v1", "secret", retries=0, opener=opener)
        self.assertEqual(client.list_models(), ["model-a", "model-b"])
        self.assertEqual(seen["url"], "http://router/v1/models")
        self.assertEqual(seen["method"], "GET")
        self.assertEqual(seen["auth"], "Bearer secret")
        self.assertEqual(seen["size"], 1_048_577)

    def test_model_list_rejects_invalid_empty_and_oversized_catalogs(self):
        for payload, message in ((b'{"data":[]}', "no models"),
                                 (b'{"data":[{"id":"x"},{"id":" "}]}', "invalid model"),
                                 (json.dumps({"data":[{"id":str(i)} for i in range(1001)]}).encode(), "too many")):
            class Response:
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self, size=-1): return payload[:size]
            client = NineRouterClient("http://router/v1", "secret", retries=0,
                                      opener=lambda request, timeout: Response())
            with self.subTest(message=message), self.assertRaisesRegex(ProviderError, message):
                client.list_models()
        class Oversized:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size=-1): return b"x" * size
        client = NineRouterClient("http://router/v1", "secret", retries=0,
                                  opener=lambda request, timeout: Oversized())
        with self.assertRaisesRegex(ProviderError, "exceeds"):
            client.list_models()

    def test_model_list_errors_are_sanitized_and_retry_policy_is_separate(self):
        for status, expected, attempts in ((401, "authentication failed", 1),
                                           (404, "not found", 1),
                                           (503, "HTTP 503", 2)):
            count = 0
            def fail(request, timeout):
                nonlocal count
                count += 1
                raise HTTPError(request.full_url, status, "secret raw provider body", None, None)
            client = NineRouterClient("http://router/v1", "top-secret", retries=1, opener=fail)
            with self.subTest(status=status):
                with self.assertRaises(ProviderError) as caught:
                    client.list_models()
            self.assertIn(expected, str(caught.exception))
            self.assertNotIn("top-secret", str(caught.exception))
            self.assertNotIn("raw provider body", str(caught.exception))
            self.assertEqual(count, attempts)

    def test_sends_chat_and_tool_schema_to_openai_compatible_endpoint(self):
        seen = {}
        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["auth"] = request.get_header("Authorization")
            seen["body"] = json.loads(request.data)
            class Response:
                status = 200
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self): return b'{"choices":[{"message":{"content":"ok"}}]}'
            return Response()
        client = NineRouterClient("http://router/v1", "secret", timeout=2, retries=0, opener=opener)
        answer = client.chat("model-x", [{"role": "user", "content": "hi"}], [{"type": "function", "function": {"name": "list_files"}}])
        self.assertEqual(answer["choices"][0]["message"]["content"], "ok")
        self.assertEqual(seen["url"], "http://router/v1/chat/completions")
        self.assertEqual(seen["auth"], "Bearer secret")
        self.assertEqual(seen["body"]["tools"][0]["function"]["name"], "list_files")

    def test_provider_error_never_includes_api_key(self):
        def fail(request, timeout):
            raise OSError("offline")
        client = NineRouterClient("http://router/v1", "secret", timeout=1, retries=0, opener=fail)
        with self.assertRaises(ProviderError) as caught:
            client.chat("model", [{"role": "user", "content": "hi"}])
        self.assertNotIn("secret", str(caught.exception))

    def test_retries_only_provider_request(self):
        count=0
        def fail(request, timeout):
            nonlocal count
            count+=1
            raise OSError("offline")
        client=NineRouterClient("http://router/v1","secret",timeout=1,retries=2,opener=fail)
        with self.assertRaises(ProviderError): client.chat("model",[{"role":"user","content":"hi"}])
        self.assertEqual(count,3)

    def test_auth_and_missing_model_fail_without_retry(self):
        for status,expected in ((401,"authentication failed"),(404,"model was not found")):
            count=0
            def fail(request,timeout):
                nonlocal count
                count+=1
                raise HTTPError(request.full_url,status,"private response body",None,None)
            client=NineRouterClient("http://router/v1","secret",timeout=1,retries=3,opener=fail)
            with self.assertRaises(ProviderError) as caught:
                client.chat("model",[{"role":"user","content":"hello"}])
            self.assertIn(expected,str(caught.exception))
            self.assertNotIn("private response",str(caught.exception))
            self.assertEqual(count,1)


class RuntimeTests(unittest.TestCase):
    def test_checkpointed_tool_loop_and_resume_do_not_repeat_completed_task(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"repo"; root.mkdir()
            store=Store(Path(temp)/"state.sqlite3")
            class Config:
                workspace=root
                model="model-a"
                fallback_model=None
                max_requests=4
                max_seconds=20
                allow_commands=()
            class Client:
                calls=0
                def chat(self, model, messages, tools):
                    self.calls+=1
                    if self.calls==1:
                        return {"model":"actual-model","choices":[{"message":{"role":"assistant","tool_calls":[{"id":"call1","type":"function","function":{"name":"write_file","arguments":json.dumps({"path":"new.txt","content":"done"})}}]}}]}
                    return {"model":"actual-model","choices":[{"message":{"role":"assistant","content":"finished"}}]}
            client=Client(); runtime=Runtime(Config(),client,store)
            task,session=runtime.new_task("create a file")
            self.assertTrue(task and session)
            self.assertEqual(runtime.run(task),"finished")
            self.assertEqual((root/"new.txt").read_text(),"done")
            self.assertEqual(runtime.run(task,resume=True),"Task already completed; no action repeated.")
            self.assertEqual(client.calls,2)
            self.assertEqual(store.task(task)["model"],"actual-model")
            self.assertEqual(store.task(task)["status"],"completed")
            self.assertFalse(any("secret" in json.dumps(event["payload"]) for event in store.events(task)))
            store.close()

    def test_store_redacts_configured_secret_from_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/"state.sqlite3")
            store.add_secret("sensitive-value")
            task,_=store.create_task(temp,"safe",None)
            store.event(task,"sample",{"text":"key=sensitive-value"})
            self.assertEqual(store.events(task)[0]["payload"]["text"],"key=[REDACTED]")
            store.close()

    def test_store_redacts_configured_secret_from_task_request(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/"state.sqlite3")
            store.add_secret("sensitive-value")
            task,_=store.create_task(temp,"please use sensitive-value",None)
            self.assertEqual(store.task(task)["request"],"please use [REDACTED]")
            store.close()

    def test_provider_failure_after_tool_action_resumes_without_repeating_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"repo"; root.mkdir()
            store=Store(Path(temp)/"state.sqlite3")
            class Config:
                workspace=root; model="model"; fallback_model=None; max_requests=4; max_seconds=20
                allow_commands=(); api_key="api-key"
            class Client:
                calls=0
                def chat(self,model,messages,tools):
                    self.calls+=1
                    if self.calls==1:
                        return {"model":"model","choices":[{"message":{"role":"assistant","tool_calls":[{"id":"write-once","function":{"name":"write_file","arguments":json.dumps({"path":"once.txt","content":"one"})}}]}}]}
                    if self.calls==2: raise ProviderError("temporary failure")
                    return {"model":"model","choices":[{"message":{"role":"assistant","content":"done"}}]}
            runtime=Runtime(Config(),Client(),store)
            task,_=runtime.new_task("write once")
            with self.assertRaises(ProviderError): runtime.run(task)
            self.assertEqual((root/"once.txt").read_text(),"one")
            self.assertEqual(runtime.run(task,resume=True),"done")
            actions=[e for e in store.events(task) if e["kind"]=="assistant_tool_call"]
            self.assertEqual(len(actions),1)
            store.close()

    def test_resume_refuses_changed_repository_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); store=Store(Path(temp)/"state.sqlite3")
            class Config:
                workspace=root; model="model"; fallback_model=None; max_requests=2; max_seconds=10; allow_commands=(); api_key="k"
            runtime=Runtime(Config(),None,store)
            task,_=runtime.new_task("work")
            runtime._workspace_identity=lambda workspace=None:{"repository":root.name,"revision":"changed"}
            with self.assertRaisesRegex(ValueError,"revision changed"):
                runtime.run(task,resume=True)
            store.close()

    def test_resume_uses_workspace_saved_on_task(self):
        with tempfile.TemporaryDirectory() as temp:
            default = Path(temp) / "default"
            selected = Path(temp) / "selected workspace"
            default.mkdir(); selected.mkdir()
            store = Store(Path(temp) / "state.sqlite3")
            class Config:
                workspace=default; model="model"; fallback_model=None; max_requests=3; max_seconds=20; allow_commands=(); api_key="test-secret-value"
            class Client:
                def __init__(self): self.calls=0
                def chat(self, model, messages, tools):
                    self.calls += 1
                    if self.calls == 1:
                        return {"model":"model","choices":[{"message":{"role":"assistant","tool_calls":[{"id":"write-selected","type":"function","function":{"name":"write_file","arguments":json.dumps({"path":"selected.txt","content":"correct workspace"})}}]}}]}
                    return {"model":"model","choices":[{"message":{"role":"assistant","content":"done"}}]}
            runtime=Runtime(Config(),Client(),store)
            task,_=runtime.new_task("write in selected", workspace=selected, name="Selected folder task")
            store.set_status(task,"paused")
            self.assertEqual(runtime.run(task,resume=True),"done")
            self.assertEqual((selected/"selected.txt").read_text(),"correct workspace")
            self.assertFalse((default/"selected.txt").exists())
            store.close()

    def test_fallback_requires_confirmed_tool_calling_capability(self):
        with tempfile.TemporaryDirectory() as temp:
            class Config:
                workspace=Path.cwd(); model="primary"; fallback_model="secondary"; max_requests=2; max_seconds=10; allow_commands=(); api_key="k"
                fallback_tool_calling=False
            class Client:
                def __init__(self): self.calls=[]
                def chat(self,model,messages,tools):
                    self.calls.append(model)
                    if model=="primary": raise ProviderError("offline")
                    return {"model":model,"choices":[{"message":{"content":"ok"}}]}
            client=Client(); store=Store(Path(temp)/"state.sqlite3"); runtime=Runtime(Config(),client,store)
            with self.assertRaises(ProviderError): runtime._request([],[],"primary")
            self.assertEqual(client.calls,["primary"])
            Config.fallback_tool_calling=True
            answer=runtime._request([],[],"primary")
            self.assertEqual(answer["model"],"secondary")
            self.assertEqual(client.calls,["primary","primary","secondary"])
            store.close()

    def test_export_import_rebinds_task_to_new_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            old_root=Path(temp)/"old"; new_root=Path(temp)/"new"
            old_root.mkdir(); new_root.mkdir()
            export=Path(temp)/"export.json"
            old_home=Path(temp)/"old-home"; old_home.mkdir()
            with patch.dict(os.environ,{"AGENT_HARNESS_HOME":str(old_home),"AGENT_HARNESS_MODEL":"model","AGENT_HARNESS_API_KEY":"api"},clear=True):
                store=Store(old_home/"state.sqlite3")
                task,_=store.create_task(old_root,"example", "model", "Exported task name")
                store.event(task,"user_request",{"content":"example"})
                store.close()
                self.assertEqual(main(["export",str(export)]),0)
            new_home=Path(temp)/"new-home"; new_home.mkdir()
            with patch.dict(os.environ,{"AGENT_HARNESS_HOME":str(new_home),"AGENT_HARNESS_MODEL":"model","AGENT_HARNESS_API_KEY":"api"},clear=True):
                self.assertEqual(main(["--workspace",str(new_root),"import",str(export)]),0)
                imported=Store(new_home/"state.sqlite3")
                self.assertEqual(imported.all_tasks()[0]["workspace"],str(new_root.resolve()))
                self.assertEqual(imported.all_tasks()[0]["name"],"Exported task name")
                self.assertEqual(imported.all_tasks()[0]["status"],"paused")
                class Config:
                    workspace=new_root.resolve(); model="model"; fallback_model=None; max_requests=3; max_seconds=20; allow_commands=(); api_key="api"
                runtime=Runtime(Config(),None,imported)
                with self.assertRaisesRegex(ValueError,"no saved Git revision"):
                    runtime.run(imported.all_tasks()[0]["id"],resume=True)
                imported.close()
            self.assertNotIn(str(old_root),export.read_text())

    def test_command_execution_is_denied_without_allowlist(self):
        with tempfile.TemporaryDirectory() as temp:
            from agent_harness.tools import Tools
            from agent_harness.policy import PermissionDenied
            tools=Tools(temp)
            with self.assertRaises(PermissionDenied): tools.run_command("python --version")

    def test_patch_requires_a_unique_match_and_returns_diff(self):
        with tempfile.TemporaryDirectory() as temp:
            from agent_harness.tools import Tools
            target=Path(temp)/"a.py"; target.write_text("value = 1\n")
            tools=Tools(temp)
            result=tools.apply_patch("a.py","value = 1","value = 2")
            self.assertIn("value = 2",target.read_text())
            self.assertIn("-value = 1",result)
            target.write_text("value = 2\nvalue = 2\n")
            with self.assertRaisesRegex(ValueError,"exactly one"):
                tools.apply_patch("a.py","value = 2","item")

    def test_default_file_listing_includes_root_and_nested_files(self):
        with tempfile.TemporaryDirectory() as temp:
            from agent_harness.tools import Tools
            (Path(temp)/"root.md").write_text("root")
            (Path(temp)/"folder").mkdir()
            (Path(temp)/"folder"/"nested.md").write_text("nested")
            files=Tools(temp).list_files().splitlines()
            self.assertIn("root.md",files)
            self.assertIn("folder/nested.md",files)

    def test_git_tools_return_concise_message_outside_a_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            from agent_harness.tools import Tools
            tools=Tools(temp)
            self.assertEqual(tools.git_status(),"Git status unavailable (workspace may not be a Git repository).")
            self.assertEqual(tools.git_diff(),"Git status unavailable (workspace may not be a Git repository).")


if __name__ == "__main__":
    unittest.main()
