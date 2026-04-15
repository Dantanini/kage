"""Repo Manager — dynamic repo registry with clone support.

Manages the list of available repos for kage to work with.
Built-in repos (journal, kage, home) cannot be removed.
User-added repos are persisted to a JSON file.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Default repos — always available, cannot be removed
_BUILTIN_REPOS = {
    "journal": str(Path(os.environ.get("DEV_JOURNAL_PATH", "")) or Path.home() / "dev-journal"),
    "kage": str(Path.home() / "kage"),
    "home": str(Path.home()),
}

_BUILTIN_NAMES = frozenset(_BUILTIN_REPOS.keys())


def extract_repo_name(url: str) -> str:
    """Extract repo name from a git URL (HTTPS or SSH)."""
    url = url.rstrip("/")
    # Handle .git suffix
    if url.endswith(".git"):
        url = url[:-4]
    # SSH format: git@github.com:user/repo
    if ":" in url and not url.startswith("http"):
        url = url.split(":")[-1]
    # Get last path component
    return url.split("/")[-1]


def clone_repo(url: str, base_dir: str, name: str | None = None) -> str:
    """Clone a git repo. Returns the local path.

    Args:
        url: Git clone URL (HTTPS or SSH)
        base_dir: Directory to clone into
        name: Optional custom directory name (default: extracted from URL)

    Returns:
        Absolute path to cloned repo

    Raises:
        RuntimeError: If git clone fails
    """
    repo_name = name or extract_repo_name(url)
    target_path = str(Path(base_dir) / repo_name)

    result = subprocess.run(
        ["git", "clone", url, target_path],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"clone failed: {result.stderr.strip()}")

    logger.info(f"Cloned {url} → {target_path}")
    return target_path


class RepoRegistry:
    """Dynamic registry of available repos.

    Built-in repos are always present. User-added repos are persisted
    to a JSON config file.
    """

    def __init__(self, config_path: Path | str | None = None):
        self._config_path = Path(config_path) if config_path else Path.home() / ".kage" / "repos.json"
        self._repos: dict[str, str] = dict(_BUILTIN_REPOS)
        self._load()

    def _load(self) -> None:
        """Load user-added repos from config file."""
        if self._config_path.exists():
            try:
                with open(self._config_path) as f:
                    user_repos = json.load(f)
                self._repos.update(user_repos)
                logger.info(f"Loaded {len(user_repos)} user repos from {self._config_path}")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load repo config: {e}")

    def _save(self) -> None:
        """Persist user-added repos to config file."""
        user_repos = {k: v for k, v in self._repos.items() if k not in _BUILTIN_NAMES}
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w") as f:
            json.dump(user_repos, f, indent=2)

    def add(self, name: str, path: str) -> None:
        """Register a new repo.

        Raises:
            ValueError: If name already exists
        """
        if name in self._repos:
            raise ValueError(f"Repo '{name}' already exists ({self._repos[name]})")
        self._repos[name] = path
        self._save()
        logger.info(f"Added repo: {name} → {path}")

    def remove(self, name: str) -> None:
        """Remove a user-added repo.

        Raises:
            ValueError: If trying to remove a built-in repo
            KeyError: If repo doesn't exist
        """
        if name in _BUILTIN_NAMES:
            raise ValueError(f"Cannot remove built-in repo '{name}'")
        if name not in self._repos:
            raise KeyError(f"Repo '{name}' not found")
        del self._repos[name]
        self._save()
        logger.info(f"Removed repo: {name}")

    def get_path(self, name: str) -> str | None:
        """Get path for a repo name. Returns None if not found."""
        return self._repos.get(name)

    def list_names(self) -> list[str]:
        """List all repo names."""
        return list(self._repos.keys())

    def list_all(self) -> list[dict]:
        """List all repos with details."""
        return [
            {
                "name": name,
                "path": path,
                "exists": Path(path).exists(),
                "builtin": name in _BUILTIN_NAMES,
            }
            for name, path in self._repos.items()
        ]

    def as_dict(self) -> dict[str, str]:
        """Return all repos as a dict (for backward compat)."""
        return dict(self._repos)
