"""Tests for dynamic repo management (add/clone/list)."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest


# --- repo_manager unit tests ---

class TestRepoRegistry:
    """Test the repo registry (add/remove/list/persist)."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = Path(self.tmpdir) / "repos.json"

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_default_repos_exist(self):
        from repo_manager import RepoRegistry
        registry = RepoRegistry(config_path=self.config_path)
        # Should have at least journal and kage
        names = registry.list_names()
        assert "journal" in names
        assert "kage" in names

    def test_add_repo(self):
        from repo_manager import RepoRegistry
        registry = RepoRegistry(config_path=self.config_path)
        registry.add("game", "/home/user/game")
        assert "game" in registry.list_names()
        assert registry.get_path("game") == "/home/user/game"

    def test_add_duplicate_raises(self):
        from repo_manager import RepoRegistry
        registry = RepoRegistry(config_path=self.config_path)
        registry.add("game", "/home/user/game")
        with pytest.raises(ValueError, match="already exists"):
            registry.add("game", "/other/path")

    def test_remove_repo(self):
        from repo_manager import RepoRegistry
        registry = RepoRegistry(config_path=self.config_path)
        registry.add("game", "/home/user/game")
        registry.remove("game")
        assert "game" not in registry.list_names()

    def test_remove_builtin_raises(self):
        from repo_manager import RepoRegistry
        registry = RepoRegistry(config_path=self.config_path)
        with pytest.raises(ValueError, match="built-in"):
            registry.remove("journal")

    def test_persist_and_load(self):
        from repo_manager import RepoRegistry
        registry = RepoRegistry(config_path=self.config_path)
        registry.add("game", "/home/user/game")

        # New instance should load from file
        registry2 = RepoRegistry(config_path=self.config_path)
        assert "game" in registry2.list_names()
        assert registry2.get_path("game") == "/home/user/game"

    def test_get_unknown_returns_none(self):
        from repo_manager import RepoRegistry
        registry = RepoRegistry(config_path=self.config_path)
        assert registry.get_path("nonexistent") is None

    def test_list_all(self):
        from repo_manager import RepoRegistry
        registry = RepoRegistry(config_path=self.config_path)
        registry.add("game", "/home/user/game")
        all_repos = registry.list_all()
        assert any(r["name"] == "game" and r["path"] == "/home/user/game" for r in all_repos)


class TestCloneRepo:
    """Test git clone functionality."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_clone_extracts_name_from_url(self):
        from repo_manager import extract_repo_name
        assert extract_repo_name("https://github.com/user/my-repo.git") == "my-repo"
        assert extract_repo_name("https://github.com/user/my-repo") == "my-repo"
        assert extract_repo_name("git@github.com:user/my-repo.git") == "my-repo"

    def test_clone_extracts_name_with_trailing_slash(self):
        from repo_manager import extract_repo_name
        assert extract_repo_name("https://github.com/user/my-repo/") == "my-repo"

    @patch("repo_manager.subprocess.run")
    def test_clone_calls_git(self, mock_run):
        from repo_manager import clone_repo
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        path = clone_repo("https://github.com/user/test-repo.git", base_dir=self.tmpdir)
        mock_run.assert_called_once()
        assert "git" in mock_run.call_args[0][0]
        assert "clone" in mock_run.call_args[0][0]

    @patch("repo_manager.subprocess.run")
    def test_clone_failure_raises(self, mock_run):
        from repo_manager import clone_repo
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="fatal: repository not found"
        )
        with pytest.raises(RuntimeError, match="clone failed"):
            clone_repo("https://github.com/user/bad-repo.git", base_dir=self.tmpdir)
