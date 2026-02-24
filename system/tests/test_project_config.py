"""Tests for project-specific configuration management."""

import tempfile
from pathlib import Path

import pytest

from gui.project_config import ProjectConfig, get_blank_project_defaults, BLANK_PROJECT_DEFAULTS


class TestProjectConfig:
    def test_exists_returns_false_when_no_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ProjectConfig(Path(tmp))
            assert not config.exists()

    def test_exists_returns_true_when_env_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ProjectConfig(Path(tmp))
            config.save({"TEST_KEY": "value"})
            assert config.exists()

    def test_load_returns_empty_dict_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ProjectConfig(Path(tmp))
            assert config.load() == {}

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ProjectConfig(Path(tmp))
            values = {"KEY1": "value1", "KEY2": "value2"}
            config.save(values)
            loaded = config.load()
            assert loaded["KEY1"] == "value1"
            assert loaded["KEY2"] == "value2"

    def test_get_effective_values_merges_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ProjectConfig(Path(tmp))
            config.save({"ANTHROPIC_API_KEY": "my-key"})
            effective = config.get_effective_values()
            assert effective["ANTHROPIC_API_KEY"] == "my-key"
            # Should have default values for other keys
            assert "OLLAMA_ENABLED" in effective

    def test_env_file_created_in_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = ProjectConfig(Path(tmp))
            config.save({"KEY": "value"})
            assert (Path(tmp) / ".env").exists()

    def test_load_parses_env_file_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("KEY1=value1\nKEY2=value2\n", encoding="utf-8")
            config = ProjectConfig(Path(tmp))
            loaded = config.load()
            assert loaded["KEY1"] == "value1"
            assert loaded["KEY2"] == "value2"


class TestBlankProjectDefaults:
    def test_blank_defaults_have_empty_api_keys(self):
        blank = get_blank_project_defaults()
        assert blank["ANTHROPIC_API_KEY"] == ""
        assert blank["OPENAI_API_KEY"] == ""
        assert blank["ANTHROPIC_MODEL"] == ""
        assert blank["OPENAI_MODEL"] == ""

    def test_blank_defaults_have_ollama_values(self):
        blank = get_blank_project_defaults()
        # Ollama values should be present for local execution
        assert blank["OLLAMA_ENABLED"] == "true"
        assert blank["OLLAMA_BASE_URL"] == "http://localhost:11434/v1"
        assert blank["PRIMARY_PROVIDER"] == "ollama"

    def test_blank_defaults_constant_is_dict(self):
        assert isinstance(BLANK_PROJECT_DEFAULTS, dict)
        assert "ANTHROPIC_API_KEY" in BLANK_PROJECT_DEFAULTS
