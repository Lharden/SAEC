"""Runtime config bridge for imports that resolve to the root `config` package.

This package primarily stores data assets (prompts/profiles). During static
analysis some modules resolve `import config` to this package instead of
`system/src/config.py`. We re-export the runtime symbols to keep imports
stable for both execution styles.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_runtime_config = import_module("system.src.config")

Paths = _runtime_config.Paths
LLMConfig = _runtime_config.LLMConfig
ExtractionConfig = _runtime_config.ExtractionConfig
LocalProcessingConfig = _runtime_config.LocalProcessingConfig

paths = _runtime_config.paths
llm_config = _runtime_config.llm_config
extraction_config = _runtime_config.extraction_config
local_config = _runtime_config.local_config

generate_mapping_csv = _runtime_config.generate_mapping_csv
load_mapping = _runtime_config.load_mapping
update_mapping_status = _runtime_config.update_mapping_status
get_pending_articles = _runtime_config.get_pending_articles
get_article_by_id = _runtime_config.get_article_by_id


def __getattr__(name: str) -> Any:
    return getattr(_runtime_config, name)


__all__ = [
    "Paths",
    "LLMConfig",
    "ExtractionConfig",
    "LocalProcessingConfig",
    "paths",
    "llm_config",
    "extraction_config",
    "local_config",
    "generate_mapping_csv",
    "load_mapping",
    "update_mapping_status",
    "get_pending_articles",
    "get_article_by_id",
]
