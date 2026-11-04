from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Config:
    base_url: str
    api_key: str
    model: str
    fallback_model: str | None
    fallback_tool_calling: bool
    timeout: float
    retries: int
    max_requests: int
    max_seconds: int
    workspace: Path
    data_dir: Path
    allow_commands: tuple[str, ...]

    @classmethod
    def from_env(cls, workspace: str | Path | None = None):
        model = os.getenv("AGENT_HARNESS_MODEL", "").strip()
        if not model:
            raise ValueError("Set AGENT_HARNESS_MODEL to a model configured in 9Router")
        key = os.getenv("AGENT_HARNESS_API_KEY", "")
        if not key:
            raise ValueError("Set AGENT_HARNESS_API_KEY from your 9Router dashboard")
        root = Path(workspace or os.getenv("AGENT_HARNESS_WORKSPACE", Path.cwd())).expanduser().resolve()
        home = Path(os.getenv("AGENT_HARNESS_HOME", Path.home() / ".haness-9router")).expanduser()
        timeout=float(os.getenv("AGENT_HARNESS_TIMEOUT", "60"))
        retries=int(os.getenv("AGENT_HARNESS_RETRIES", "2"))
        max_requests=int(os.getenv("AGENT_HARNESS_MAX_REQUESTS", "24"))
        max_seconds=int(os.getenv("AGENT_HARNESS_MAX_SECONDS", "900"))
        if timeout<=0 or not 0<=retries<=10 or max_requests<=0 or max_seconds<=0:
            raise ValueError("Timeout, retry, request, and task time limits are outside allowed ranges")
        return cls(
            base_url=os.getenv("AGENT_HARNESS_BASE_URL", "http://localhost:20128/v1").rstrip("/"),
            api_key=key, model=model, fallback_model=os.getenv("AGENT_HARNESS_FALLBACK_MODEL") or None,
            fallback_tool_calling=os.getenv("AGENT_HARNESS_FALLBACK_TOOL_CALLING", "false").lower() in {"1","true","yes"},
            timeout=timeout, retries=retries, max_requests=max_requests, max_seconds=max_seconds,
            workspace=root, data_dir=home,
            allow_commands=tuple(x.strip() for x in os.getenv("AGENT_HARNESS_ALLOW_COMMANDS", "").split(",") if x.strip()),
        )
