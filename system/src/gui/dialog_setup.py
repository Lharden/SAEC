"""First-run setup dialog for providers and model routing."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from typing import Callable

try:
    from urllib.error import URLError
    from urllib.request import urlopen
except ImportError:  # pragma: no cover
    URLError = OSError  # type: ignore[misc,assignment]

    def urlopen(*args, **kwargs):  # type: ignore[override]
        raise URLError("urllib not available")

from gui.i18n import t, get_language, set_language, available_languages

ROUTING_FIELDS: list[tuple[str, str, str]] = [
    (
        "Main extraction (Ollama text/cloud)",
        "OLLAMA_MODEL_CLOUD",
        "Model used for local/cloud extraction in hybrid flows.",
    ),
    (
        "Extraction fallback (Ollama)",
        "OLLAMA_MODEL_CLOUD_FALLBACK",
        "Second model when primary extraction model fails.",
    ),
    (
        "Vision pages (Ollama multimodal)",
        "OLLAMA_MODEL_VISION",
        "Model used when image blocks/pages are sent.",
    ),
    (
        "YAML formatter / postprocess",
        "OLLAMA_MODEL_CODER",
        "Model used in formatting and deterministic correction stages.",
    ),
    (
        "Cascade extraction (local)",
        "OLLAMA_EXTRACTION_MODEL",
        "Model used by cascade local extraction attempts.",
    ),
    (
        "Cascade repair (local)",
        "OLLAMA_REPAIR_MODEL",
        "Model used by cascade local repair attempts.",
    ),
    (
        "OCR model",
        "OLLAMA_OCR_MODEL",
        "Model used for OCR-specific tasks in local flows.",
    ),
    (
        "RAG embedding",
        "OLLAMA_EMBEDDING_MODEL",
        "Model used to generate embeddings for retrieval.",
    ),
    (
        "Reranker model",
        "OLLAMA_RERANKER_MODEL",
        "Model used for passage reranking in RAG.",
    ),
]

PROVIDER_ROUTING_FIELDS: list[tuple[str, str, str, tuple[str, ...]]] = [
    (
        "Main extraction",
        "PROVIDER_EXTRACT",
        "Provider for main article extraction.",
        ("auto", "ollama", "openai", "anthropic"),
    ),
    (
        "YAML repair",
        "PROVIDER_REPAIR",
        "Provider for schema/validation repair pass.",
        ("auto", "ollama", "openai", "anthropic"),
    ),
    (
        "Quote recheck",
        "PROVIDER_QUOTES",
        "Provider for quote recovery/recheck attempts.",
        ("auto", "ollama", "openai", "anthropic"),
    ),
    (
        "Cascade API escalation",
        "PROVIDER_CASCADE_API",
        "Provider used when cascade escalates to API.",
        ("auto", "openai", "anthropic"),
    ),
]

# Groups for Ollama model assignment display in Tab 2
_MODEL_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Extraction",
        [
            ("OLLAMA_MODEL_CLOUD", "Main extraction"),
            ("OLLAMA_MODEL_CLOUD_FALLBACK", "Extraction fallback"),
        ],
    ),
    (
        "Processing",
        [
            ("OLLAMA_MODEL_VISION", "Vision pages"),
            ("OLLAMA_MODEL_CODER", "YAML formatter"),
        ],
    ),
    (
        "Cascade",
        [
            ("OLLAMA_EXTRACTION_MODEL", "Cascade extraction"),
            ("OLLAMA_REPAIR_MODEL", "Cascade repair"),
        ],
    ),
    (
        "Utilities",
        [
            ("OLLAMA_OCR_MODEL", "OCR model"),
            ("OLLAMA_EMBEDDING_MODEL", "RAG embedding"),
            ("OLLAMA_RERANKER_MODEL", "Reranker"),
        ],
    ),
]


DEFAULT_VALUES: dict[str, str] = {
    "ANTHROPIC_API_KEY": "",
    "OPENAI_API_KEY": "",
    "OPENAI_BASE_URL": "",
    "ANTHROPIC_MODEL": "",
    "OPENAI_MODEL": "",
    "OLLAMA_ENABLED": "true",
    "OLLAMA_BASE_URL": "http://localhost:11434/v1",
    "PRIMARY_PROVIDER": "ollama",
    "PROVIDER_EXTRACT": "auto",
    "PROVIDER_REPAIR": "auto",
    "PROVIDER_QUOTES": "anthropic",
    "PROVIDER_CASCADE_API": "openai",
    "USE_TWO_PASS": "true",
    "OLLAMA_MODEL_CLOUD": "qwen3-coder-next:cloud",
    "OLLAMA_MODEL_CLOUD_FALLBACK": "glm-5:cloud",
    "OLLAMA_MODEL_CODER": "qwen3-coder-next:cloud",
    "OLLAMA_MODEL_VISION": "qwen3-vl:8b",
    "OLLAMA_EXTRACTION_MODEL": "qwen3-coder-next:cloud",
    "OLLAMA_REPAIR_MODEL": "glm-4.7:cloud",
    "OLLAMA_OCR_MODEL": "glm-ocr:latest",
    "OLLAMA_EMBEDDING_MODEL": "nomic-embed-text-v2-moe:latest",
    "OLLAMA_RERANKER_MODEL": "qllama/bge-reranker-v2-m3:q4_k_m",
    "GUI_LANGUAGE": "pt-BR",
}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _create_help_label(parent: tk.Misc, text: str) -> ttk.Label:
    """Small gray helper text."""
    label = ttk.Label(parent, text=text, foreground="gray")
    return label


def _bool_from_env(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes")


def _merge_choices(existing: list[str], extras: list[str]) -> list[str]:
    """Merge existing combo choices with new entries, deduplicating."""
    seen: set[str] = set()
    result: list[str] = []
    for item in existing + extras:
        key = item.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _guess_model_capabilities(name: str) -> str:
    """Guess capabilities from model name for display."""
    lower = name.lower()
    caps: list[str] = []
    if "cloud" in lower:
        caps.append("cloud")
    if "embed" in lower:
        caps.append("embedding")
    elif "rerank" in lower:
        caps.append("reranking")
    elif "vl" in lower or "vision" in lower:
        caps.append("vision")
    elif "ocr" in lower:
        caps.append("ocr")
    if not caps:
        caps.append("text")
    return ", ".join(caps)


def _probe_ollama_models(base_url: str) -> list[str]:
    """Probe Ollama for available model names."""
    try:
        api_url = base_url.rstrip("/")
        if api_url.endswith("/v1"):
            api_url = api_url[:-3]
        url = f"{api_url}/api/tags"
        with urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        models = data.get("models", [])
        names: list[str] = []
        for m in models:
            name = m.get("model") or m.get("name", "")
            if name:
                names.append(name)
        return sorted(names)
    except Exception:
        return []


# ------------------------------------------------------------------
# UI Sections
# ------------------------------------------------------------------

def _build_welcome_section(frame: ttk.Frame) -> None:
    """Add welcome header to the settings dialog."""
    ttk.Label(
        frame,
        text=t("setup.welcome_title"),
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w", pady=(0, 4))
    ttk.Label(
        frame,
        text=t("setup.welcome_subtitle"),
        wraplength=520,
    ).pack(anchor="w", pady=(0, 8))


def _build_provider_section(
    frame: ttk.Frame,
    *,
    values: dict[str, str],
    ollama_models: list[str],
    combos: dict[str, ttk.Combobox],
) -> None:
    """Build provider credentials + model routing section."""
    # --- API Keys ---
    key_frame = ttk.LabelFrame(frame, text=t("setup.api_keys"))
    key_frame.pack(fill="x", pady=(0, 8))

    for label_text, env_key in [
        ("Anthropic API Key", "ANTHROPIC_API_KEY"),
        ("OpenAI API Key", "OPENAI_API_KEY"),
    ]:
        row = ttk.Frame(key_frame)
        row.pack(fill="x", padx=8, pady=2)
        ttk.Label(row, text=label_text, width=20).pack(side="left")
        entry = ttk.Entry(row, show="*")
        entry.insert(0, values.get(env_key, ""))
        entry.pack(side="left", fill="x", expand=True)
        combos[env_key] = entry  # type: ignore[assignment]

    for label_text, env_key in [
        ("Anthropic Model", "ANTHROPIC_MODEL"),
        ("OpenAI Model", "OPENAI_MODEL"),
    ]:
        row = ttk.Frame(key_frame)
        row.pack(fill="x", padx=8, pady=2)
        ttk.Label(row, text=label_text, width=20).pack(side="left")
        entry = ttk.Entry(row)
        entry.insert(0, values.get(env_key, ""))
        entry.pack(side="left", fill="x", expand=True)
        combos[env_key] = entry  # type: ignore[assignment]

    # --- Provider Routing ---
    prov_frame = ttk.LabelFrame(frame, text=t("setup.provider_routing"))
    prov_frame.pack(fill="x", pady=(0, 8))

    for label_text, env_key, tooltip, choices in PROVIDER_ROUTING_FIELDS:
        row = ttk.Frame(prov_frame)
        row.pack(fill="x", padx=8, pady=2)
        ttk.Label(row, text=label_text, width=20).pack(side="left")
        combo = ttk.Combobox(row, values=list(choices), state="readonly", width=15)
        current = values.get(env_key, choices[0])
        if current in choices:
            combo.set(current)
        else:
            combo.set(choices[0])
        combo.pack(side="left")
        _create_help_label(row, tooltip).pack(side="left", padx=8)
        combos[env_key] = combo

    # --- Ollama URL ---
    url_frame = ttk.LabelFrame(frame, text="Ollama")
    url_frame.pack(fill="x", pady=(0, 8))

    url_row = ttk.Frame(url_frame)
    url_row.pack(fill="x", padx=8, pady=2)
    ttk.Label(url_row, text="Base URL", width=20).pack(side="left")
    url_entry = ttk.Entry(url_row)
    url_entry.insert(0, values.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
    url_entry.pack(side="left", fill="x", expand=True)
    combos["OLLAMA_BASE_URL"] = url_entry  # type: ignore[assignment]

    # --- Model Assignments ---
    model_frame = ttk.LabelFrame(frame, text=t("setup.model_assignments"))
    model_frame.pack(fill="x", pady=(0, 8))

    for group_name, fields in _MODEL_GROUPS:
        ttk.Label(model_frame, text=group_name, font=("Segoe UI", 9, "bold")).pack(
            anchor="w", padx=8, pady=(6, 2)
        )
        for env_key, display_name in fields:
            row = ttk.Frame(model_frame)
            row.pack(fill="x", padx=16, pady=1)
            ttk.Label(row, text=display_name, width=20).pack(side="left")
            model_choices = _merge_choices(
                ollama_models, [values.get(env_key, DEFAULT_VALUES.get(env_key, ""))]
            )
            combo = ttk.Combobox(row, values=model_choices, width=30)
            combo.set(values.get(env_key, DEFAULT_VALUES.get(env_key, "")))
            combo.pack(side="left", fill="x", expand=True)
            combos[env_key] = combo

    # Refresh button
    def _refresh_models() -> None:
        url = combos.get("OLLAMA_BASE_URL")
        base = url.get() if url else "http://localhost:11434/v1"  # type: ignore[union-attr]
        models = _probe_ollama_models(base)
        for _group_name, fields in _MODEL_GROUPS:
            for env_key, _display_name in fields:
                combo = combos.get(env_key)
                if combo and isinstance(combo, ttk.Combobox):
                    current_val = combo.get()
                    new_choices = _merge_choices(models, [current_val])
                    combo.configure(values=new_choices)

    ttk.Button(model_frame, text=t("setup.refresh_models"), command=_refresh_models).pack(
        anchor="e", padx=8, pady=4
    )

    # --- Language selector ---
    lang_frame = ttk.LabelFrame(frame, text=t("setup.language"))
    lang_frame.pack(fill="x", pady=(0, 8))

    lang_row = ttk.Frame(lang_frame)
    lang_row.pack(fill="x", padx=8, pady=4)
    ttk.Label(lang_row, text=t("setup.gui_language"), width=20).pack(side="left")
    langs = available_languages()
    lang_combo = ttk.Combobox(lang_row, values=langs, state="readonly", width=15)
    current_lang = values.get("GUI_LANGUAGE", get_language())
    if current_lang in langs:
        lang_combo.set(current_lang)
    else:
        lang_combo.set(langs[0] if langs else "pt-BR")
    lang_combo.pack(side="left")
    combos["GUI_LANGUAGE"] = lang_combo
    _create_help_label(lang_row, t("setup.language_restart_hint")).pack(
        side="left", padx=8
    )


def _build_workspace_section(
    frame: ttk.Frame,
    *,
    values: dict[str, str],
    combos: dict[str, ttk.Combobox],
) -> None:
    """Build strategy/workspace section."""
    strat_frame = ttk.LabelFrame(frame, text=t("setup.strategy"))
    strat_frame.pack(fill="x", pady=(0, 8))

    row = ttk.Frame(strat_frame)
    row.pack(fill="x", padx=8, pady=2)
    ttk.Label(row, text="Primary Provider", width=20).pack(side="left")
    pp_combo = ttk.Combobox(
        row, values=["ollama", "openai", "anthropic"], state="readonly", width=15
    )
    pp_combo.set(values.get("PRIMARY_PROVIDER", "ollama"))
    pp_combo.pack(side="left")
    combos["PRIMARY_PROVIDER"] = pp_combo

    row2 = ttk.Frame(strat_frame)
    row2.pack(fill="x", padx=8, pady=2)
    two_pass_var = tk.BooleanVar(value=_bool_from_env(values.get("USE_TWO_PASS", "true")))
    ttk.Checkbutton(row2, text="Two-pass extraction", variable=two_pass_var).pack(
        side="left"
    )
    combos["USE_TWO_PASS"] = two_pass_var  # type: ignore[assignment]


# ------------------------------------------------------------------
# Main dialog function
# ------------------------------------------------------------------


def prompt_first_run_setup(
    parent: tk.Misc,
    *,
    default_ollama_url: str = "http://localhost:11434/v1",
    existing_values: dict[str, str] | None = None,
) -> dict[str, str] | None:
    """
    Show settings dialog and return dict of env values, or None if cancelled.

    Args:
        parent: Parent Tk widget
        default_ollama_url: Default Ollama base URL
        existing_values: Pre-existing .env values for edit mode

    Returns:
        Dict of env key-value pairs, or None if user cancelled.
    """
    values = dict(DEFAULT_VALUES)
    if existing_values:
        values.update(existing_values)
    if "OLLAMA_BASE_URL" not in values:
        values["OLLAMA_BASE_URL"] = default_ollama_url

    result: dict[str, str] | None = None
    dialog = tk.Toplevel(parent)
    dialog.title(t("setup.dialog_title"))
    dialog.geometry("640x620")
    dialog.resizable(True, True)
    dialog.transient(parent)
    dialog.grab_set()

    # Scrollable content
    canvas = tk.Canvas(dialog, highlightthickness=0)
    scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
    content = ttk.Frame(canvas)

    content.bind(
        "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.create_window((0, 0), window=content, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Mouse wheel scrolling
    def _on_mousewheel(event: tk.Event) -> None:  # type: ignore[type-arg]
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    combos: dict[str, ttk.Combobox] = {}

    # Probe models
    ollama_models = _probe_ollama_models(values.get("OLLAMA_BASE_URL", default_ollama_url))

    # Build UI sections
    padding_frame = ttk.Frame(content)
    padding_frame.pack(fill="both", expand=True, padx=16, pady=8)

    _build_welcome_section(padding_frame)
    _build_provider_section(
        padding_frame, values=values, ollama_models=ollama_models, combos=combos
    )
    _build_workspace_section(padding_frame, values=values, combos=combos)

    # --- Buttons ---
    btn_frame = ttk.Frame(padding_frame)
    btn_frame.pack(fill="x", pady=(8, 0))

    def _on_save() -> None:
        nonlocal result
        collected: dict[str, str] = {}
        for key, widget in combos.items():
            if isinstance(widget, tk.BooleanVar):
                collected[key] = "true" if widget.get() else "false"
            elif hasattr(widget, "get"):
                collected[key] = widget.get().strip()
        # Apply language change
        lang = collected.get("GUI_LANGUAGE", "")
        if lang:
            set_language(lang)
        result = collected
        canvas.unbind_all("<MouseWheel>")
        dialog.destroy()

    def _on_cancel() -> None:
        nonlocal result
        result = None
        canvas.unbind_all("<MouseWheel>")
        dialog.destroy()

    ttk.Button(btn_frame, text=t("setup.save"), command=_on_save).pack(
        side="right", padx=4
    )
    ttk.Button(btn_frame, text=t("setup.cancel"), command=_on_cancel).pack(side="right")

    dialog.protocol("WM_DELETE_WINDOW", _on_cancel)
    dialog.wait_window()

    return result
