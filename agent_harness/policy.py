from pathlib import Path


class PermissionDenied(Exception):
    pass


class WorkspacePolicy:
    """Path guard for file tools; it does not sandbox subprocesses."""
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Workspace must be an existing directory")

    def resolve(self, relative: str, *, allow_missing: bool = False) -> Path:
        supplied = Path(relative)
        if supplied.is_absolute():
            raise PermissionDenied("Absolute paths are not allowed")
        candidate = self.root / supplied
        try:
            resolved = candidate.resolve(strict=not allow_missing)
            resolved.relative_to(self.root)
        except (OSError, ValueError, RuntimeError) as exc:
            raise PermissionDenied("Path is outside the workspace or unavailable") from exc
        if resolved.exists() and not resolved.is_file() and not resolved.is_dir():
            raise PermissionDenied("Special files are not allowed")
        return resolved
