"""Setup dialog — Credentials, Providers & Models (tabbed UI)."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import cast

from urllib.request import urlopen


from gui.i18n import t, get_language, set_language, available_languages

# ── Constants ──────────────────────────────────────────────────────

ROUTING_FIELDS: list[tuple[str, str, str]] = [
    ("OLLAMA_MODEL_CLOUD", "setup.model_main", "setup.route_extract_help"),
    ("OLLAMA_MODEL_CLOUD_FALLBACK", "setup.model_fallback", "setup.route_extract_help"),
    ("OLLAMA_MODEL_VISION", "setup.model_vision", "setup.route_extract_help"),
    ("OLLAMA_MODEL_CODER", "setup.model_coder", "setup.route_extract_help"),
    ("OLLAMA_EXTRACTION_MODEL", "setup.model_cascade_extract", "setup.route_extract_help"),
    ("OLLAMA_REPAIR_MODEL", "setup.model_cascade_repair", "setup.route_repair_help"),
    ("OLLAMA_OCR_MODEL", "setup.model_ocr", "setup.route_extract_help"),
    ("OLLAMA_EMBEDDING_MODEL", "setup.model_embedding", "setup.route_extract_help"),
    ("OLLAMA_RERANKER_MODEL", "setup.model_reranker", "setup.route_extract_help"),
]

PROVIDER_ROUTING_FIELDS: list[tuple[str, str, str, tuple[str, ...]]] = [
    (
        "PROVIDER_EXTRACT",
        "setup.route_extract",
        "setup.route_extract_help",
        ("auto", "ollama", "openai", "anthropic"),
    ),
    (
        "PROVIDER_REPAIR",
        "setup.route_repair",
        "setup.route_repair_help",
        ("auto", "ollama", "openai", "anthropic"),
    ),
    (
        "PROVIDER_QUOTES",
        "setup.route_quotes",
        "setup.route_quotes_help",
        ("auto", "ollama", "openai", "anthropic"),
    ),
    (
        "PROVIDER_CASCADE_API",
        "setup.route_cascade_api",
        "setup.route_cascade_api_help",
        ("auto", "openai", "anthropic"),
    ),
]

_MODEL_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "setup.group_extraction",
        [
            ("OLLAMA_MODEL_CLOUD", "setup.model_main"),
            ("OLLAMA_MODEL_CLOUD_FALLBACK", "setup.model_fallback"),
        ],
    ),
    (
        "setup.group_processing",
        [
            ("OLLAMA_MODEL_VISION", "setup.model_vision"),
            ("OLLAMA_MODEL_CODER", "setup.model_coder"),
        ],
    ),
    (
        "setup.group_cascade",
        [
            ("OLLAMA_EXTRACTION_MODEL", "setup.model_cascade_extract"),
            ("OLLAMA_REPAIR_MODEL", "setup.model_cascade_repair"),
        ],
    ),
    (
        "setup.group_utilities",
        [
            ("OLLAMA_OCR_MODEL", "setup.model_ocr"),
            ("OLLAMA_EMBEDDING_MODEL", "setup.model_embedding"),
            ("OLLAMA_RERANKER_MODEL", "setup.model_reranker"),
        ],
    ),
]

DEFAULT_VALUES: dict[str, str] = {
    "ANTHROPIC_API_KEY": "",
    "OPENAI_API_KEY": "",
    "OPENAI_BASE_URL": "",
    "LLM_PROVIDERS_FILE": "config/providers.yaml",
    "ANTHROPIC_MODEL": "",
    "OPENAI_MODEL": "",
    "OLLAMA_ENABLED": "true",
    "OLLAMA_BASE_URL": "http://localhost:11434/v1",
    "PRIMARY_PROVIDER": "ollama",
    "PROVIDER_EXTRACT": "auto",
    "PROVIDER_REPAIR": "auto",
    "PROVIDER_QUOTES": "auto",
    "PROVIDER_CASCADE_API": "auto",
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


# ── Helpers ────────────────────────────────────────────────────────


def _bool_from_env(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes")


def _merge_choices(existing: list[str], extras: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in existing + extras:
        key = item.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _probe_ollama_models(base_url: str) -> list[str]:
    try:
        api_url = base_url.rstrip("/")
        if api_url.endswith("/v1"):
            api_url = api_url[:-3]
        url = f"{api_url}/api/tags"
        with urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        return sorted(
            m.get("model") or m.get("name", "")
            for m in data.get("models", [])
            if m.get("model") or m.get("name")
        )
    except Exception:
        return []


def _help_label(parent: tk.Misc, text: str) -> ttk.Label:
    return ttk.Label(parent, text=text, font=("Segoe UI", 7), foreground="#888")


def _resolve_providers_file(parent: tk.Misc, value: str) -> Path:
    raw = (value or "").strip() or "config/providers.yaml"
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate

    project_root = getattr(parent, "project_root", None)
    if isinstance(project_root, Path):
        return (project_root / candidate).resolve()

    system_root = getattr(parent, "_system_root", None)
    if isinstance(system_root, Path):
        return (system_root / candidate).resolve()

    return (Path.cwd() / candidate).resolve()


def _open_providers_editor(parent: tk.Misc, path_entry: ttk.Entry) -> None:
    target = _resolve_providers_file(parent, path_entry.get())
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(
            "providers:\n"
            "  ollama:\n"
            "    kind: ollama\n"
            "    enabled: true\n"
            "    base_url: http://localhost:11434/v1\n"
            "    model: qwen3-coder-next:cloud\n"
            "    vision_model: qwen3-vl:8b\n"
            "\n"
            "  litellm_gateway:\n"
            "    kind: openai_compatible\n"
            "    enabled: false\n"
            "    base_url: http://127.0.0.1:4000\n"
            "    api_key: litellm\n"
            "    model: glm-5\n"
            "\n"
            "  openrouter:\n"
            "    kind: openai_compatible\n"
            "    enabled: false\n"
            "    base_url: https://openrouter.ai/api/v1\n"
            "    api_key_env: OPENROUTER_API_KEY\n"
            "    model: openai/gpt-5\n",
            encoding="utf-8",
        )

    editor = tk.Toplevel(parent)
    editor.title(f"Providers YAML — {target.name}")
    editor.geometry("840x620")
    if isinstance(parent, (tk.Tk, tk.Toplevel)):
        editor.transient(cast(tk.Wm, parent))
    editor.grab_set()

    text = tk.Text(editor, wrap="none")
    text.pack(fill="both", expand=True, padx=8, pady=8)
    text.insert("1.0", target.read_text(encoding="utf-8"))

    btn_row = ttk.Frame(editor)
    btn_row.pack(fill="x", padx=8, pady=(0, 8))

    status = ttk.Label(btn_row, text=str(target), foreground="#666")
    status.pack(side="left")

    def _save() -> None:
        target.write_text(text.get("1.0", "end-1c"), encoding="utf-8")
        status.configure(text=f"Salvo em: {target}", foreground="#006400")

    ttk.Button(btn_row, text="Salvar YAML", command=_save).pack(side="right")


# ── Tab 1: Credentials & Providers ────────────────────────────────


def _build_credentials_tab(
    tab: ttk.Frame,
    values: dict[str, str],
    combos: dict[str, ttk.Combobox],
) -> None:
    """Build credentials, provider routing, and strategy controls."""

    # --- API Keys ---
    key_frame = ttk.LabelFrame(tab, text=t("setup.api_keys"))
    key_frame.pack(fill="x", padx=8, pady=(8, 4))

    for label_key, env_key, show in [
        ("setup.cloud_key_1", "ANTHROPIC_API_KEY", "*"),
        ("setup.cloud_key_2", "OPENAI_API_KEY", "*"),
    ]:
        row = ttk.Frame(key_frame)
        row.pack(fill="x", padx=8, pady=2)
        ttk.Label(row, text=t(label_key), width=28, anchor="w").pack(side="left")
        entry = ttk.Entry(row, show=show)
        entry.insert(0, values.get(env_key, ""))
        entry.pack(side="left", fill="x", expand=True)
        combos[env_key] = entry  # type: ignore[assignment]

    for label_key, env_key in [
        ("setup.cloud_model_1", "ANTHROPIC_MODEL"),
        ("setup.cloud_model_2", "OPENAI_MODEL"),
        ("setup.cloud_base_url", "OPENAI_BASE_URL"),
    ]:
        row = ttk.Frame(key_frame)
        row.pack(fill="x", padx=8, pady=2)
        ttk.Label(row, text=t(label_key), width=28, anchor="w").pack(side="left")
        entry = ttk.Entry(row)
        entry.insert(0, values.get(env_key, ""))
        entry.pack(side="left", fill="x", expand=True)
        combos[env_key] = entry  # type: ignore[assignment]

    providers_row = ttk.Frame(key_frame)
    providers_row.pack(fill="x", padx=8, pady=2)
    ttk.Label(
        providers_row,
        text="Providers YAML",
        width=28,
        anchor="w",
    ).pack(side="left")
    providers_entry = ttk.Entry(providers_row)
    providers_entry.insert(0, values.get("LLM_PROVIDERS_FILE", "config/providers.yaml"))
    providers_entry.pack(side="left", fill="x", expand=True)
    combos["LLM_PROVIDERS_FILE"] = providers_entry  # type: ignore[assignment]
    ttk.Button(
        providers_row,
        text="Editar",
        command=lambda: _open_providers_editor(tab.winfo_toplevel(), providers_entry),
    ).pack(side="left", padx=(6, 0))

    # --- Ollama ---
    ollama_frame = ttk.LabelFrame(tab, text="Ollama")
    ollama_frame.pack(fill="x", padx=8, pady=4)

    url_row = ttk.Frame(ollama_frame)
    url_row.pack(fill="x", padx=8, pady=2)
    ttk.Label(url_row, text=t("setup.ollama_url"), width=28, anchor="w").pack(side="left")
    url_entry = ttk.Entry(url_row)
    url_entry.insert(0, values.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
    url_entry.pack(side="left", fill="x", expand=True)
    combos["OLLAMA_BASE_URL"] = url_entry  # type: ignore[assignment]

    # --- Provider Strategy ---
    strat_frame = ttk.LabelFrame(tab, text=t("setup.provider_strategy"))
    strat_frame.pack(fill="x", padx=8, pady=4)

    pp_row = ttk.Frame(strat_frame)
    pp_row.pack(fill="x", padx=8, pady=2)
    ttk.Label(pp_row, text=t("setup.primary_provider"), width=28, anchor="w").pack(side="left")
    pp_combo = ttk.Combobox(
        pp_row, values=["ollama", "openai", "anthropic"], state="readonly", width=15
    )
    pp_combo.set(values.get("PRIMARY_PROVIDER", "ollama"))
    pp_combo.pack(side="left")
    combos["PRIMARY_PROVIDER"] = pp_combo

    tp_row = ttk.Frame(strat_frame)
    tp_row.pack(fill="x", padx=8, pady=2)
    two_pass_var = tk.BooleanVar(value=_bool_from_env(values.get("USE_TWO_PASS", "true")))
    ttk.Checkbutton(tp_row, text=t("setup.enable_two_pass"), variable=two_pass_var).pack(
        side="left"
    )
    combos["USE_TWO_PASS"] = two_pass_var  # type: ignore[assignment]

    # --- Provider Routing ---
    routing_frame = ttk.LabelFrame(tab, text=t("setup.routing_title"))
    routing_frame.pack(fill="x", padx=8, pady=4)
    _help_label(routing_frame, t("setup.routing_hint")).pack(anchor="w", padx=8, pady=(4, 2))

    for env_key, label_key, help_key, choices in PROVIDER_ROUTING_FIELDS:
        row = ttk.Frame(routing_frame)
        row.pack(fill="x", padx=8, pady=2)
        ttk.Label(row, text=t(label_key), width=28, anchor="w").pack(side="left")
        combo = ttk.Combobox(row, values=list(choices), width=24)
        current = values.get(env_key, choices[0])
        combo.set(current or choices[0])
        combo.pack(side="left")
        _help_label(row, t(help_key)).pack(side="left", padx=8)
        combos[env_key] = combo

    # --- Language ---
    lang_frame = ttk.LabelFrame(tab, text=t("setup.language"))
    lang_frame.pack(fill="x", padx=8, pady=(4, 8))

    lang_row = ttk.Frame(lang_frame)
    lang_row.pack(fill="x", padx=8, pady=4)
    ttk.Label(lang_row, text=t("setup.gui_language"), width=28, anchor="w").pack(side="left")
    langs = available_languages()
    lang_codes = [c for c, _ in langs]
    lang_labels = [lbl for _, lbl in langs]
    lang_combo = ttk.Combobox(lang_row, values=lang_labels, state="readonly", width=20)
    current_lang = values.get("GUI_LANGUAGE", get_language())
    idx = lang_codes.index(current_lang) if current_lang in lang_codes else 0
    lang_combo.current(idx)
    lang_combo.pack(side="left")
    combos["GUI_LANGUAGE"] = lang_combo
    combos["_lang_codes"] = lang_codes  # type: ignore[assignment]
    _help_label(lang_row, t("setup.language_restart_hint")).pack(side="left", padx=8)


# ── Tab 2: Model Assignments ──────────────────────────────────────


def _build_models_tab(
    tab: ttk.Frame,
    values: dict[str, str],
    ollama_models: list[str],
    combos: dict[str, ttk.Combobox],
) -> None:
    """Build grouped model assignment combos."""

    for group_key, fields in _MODEL_GROUPS:
        group_frame = ttk.LabelFrame(tab, text=t(group_key))
        group_frame.pack(fill="x", padx=8, pady=4)

        for env_key, label_key in fields:
            row = ttk.Frame(group_frame)
            row.pack(fill="x", padx=8, pady=2)
            ttk.Label(row, text=t(label_key), width=22, anchor="w").pack(side="left")
            default = DEFAULT_VALUES.get(env_key, "")
            current_val = values.get(env_key, default)
            model_choices = _merge_choices(ollama_models, [current_val] if current_val else [])
            combo = ttk.Combobox(row, values=model_choices, width=35)
            combo.set(current_val)
            combo.pack(side="left", fill="x", expand=True)
            combos[env_key] = combo

    # Refresh button
    def _refresh_models() -> None:
        url_widget = combos.get("OLLAMA_BASE_URL")
        base = (
            url_widget.get()
            if url_widget and hasattr(url_widget, "get")
            else "http://localhost:11434/v1"
        )
        models = _probe_ollama_models(base)
        for _group_key, fields in _MODEL_GROUPS:
            for env_key, _ in fields:
                combo = combos.get(env_key)
                if combo and isinstance(combo, ttk.Combobox):
                    cur = combo.get()
                    combo.configure(values=_merge_choices(models, [cur] if cur else []))

    btn_frame = ttk.Frame(tab)
    btn_frame.pack(fill="x", padx=8, pady=(2, 8))
    ttk.Button(btn_frame, text=t("setup.refresh_models"), command=_refresh_models).pack(
        side="right"
    )

    # Cloud API models (informational)
    cloud_frame = ttk.LabelFrame(tab, text=t("setup.cloud_models"))
    cloud_frame.pack(fill="x", padx=8, pady=(0, 8))

    for label_key, env_key in [
        ("setup.cloud_model_1", "ANTHROPIC_MODEL"),
        ("setup.cloud_model_2", "OPENAI_MODEL"),
    ]:
        row = ttk.Frame(cloud_frame)
        row.pack(fill="x", padx=8, pady=2)
        ttk.Label(row, text=t(label_key), width=22, anchor="w").pack(side="left")
        val = values.get(env_key, "")
        ttk.Label(row, text=val or "(não configurado)", foreground="#666").pack(side="left")


# ── Main dialog ───────────────────────────────────────────────────


def prompt_first_run_setup(
    parent: tk.Misc,
    *,
    default_ollama_url: str = "http://localhost:11434/v1",
    existing_values: dict[str, str] | None = None,
) -> dict[str, str] | None:
    """Show tabbed settings dialog. Returns dict of values or None if cancelled."""

    values = dict(DEFAULT_VALUES)
    if existing_values:
        values.update(existing_values)
    if "OLLAMA_BASE_URL" not in values:
        values["OLLAMA_BASE_URL"] = default_ollama_url

    result: dict[str, str] | None = None
    dialog = tk.Toplevel(parent)
    dialog.title(t("setup.dialog_title"))
    dialog.geometry("680x640")
    dialog.resizable(True, True)
    if isinstance(parent, (tk.Tk, tk.Toplevel)):
        dialog.transient(cast(tk.Wm, parent))
    dialog.grab_set()

    combos: dict[str, ttk.Combobox] = {}

    # Probe Ollama models
    ollama_models = _probe_ollama_models(values.get("OLLAMA_BASE_URL", default_ollama_url))

    # ── Notebook (tabs) ──
    notebook = ttk.Notebook(dialog)
    notebook.pack(fill="both", expand=True, padx=8, pady=(8, 0))

    # Tab 1: Credentials & Providers (scrollable)
    tab1_outer = ttk.Frame(notebook)
    notebook.add(tab1_outer, text=t("setup.tab_credentials"))

    tab1_canvas = tk.Canvas(tab1_outer, highlightthickness=0)
    tab1_scroll = ttk.Scrollbar(tab1_outer, orient="vertical", command=tab1_canvas.yview)
    tab1 = ttk.Frame(tab1_canvas)
    tab1.bind("<Configure>", lambda e: tab1_canvas.configure(scrollregion=tab1_canvas.bbox("all")))
    tab1_canvas.create_window((0, 0), window=tab1, anchor="nw")
    tab1_canvas.configure(yscrollcommand=tab1_scroll.set)
    tab1_canvas.pack(side="left", fill="both", expand=True)
    tab1_scroll.pack(side="right", fill="y")

    _build_credentials_tab(tab1, values, combos)

    # Tab 2: Model Assignments (scrollable)
    tab2_outer = ttk.Frame(notebook)
    notebook.add(tab2_outer, text=t("setup.tab_models"))

    tab2_canvas = tk.Canvas(tab2_outer, highlightthickness=0)
    tab2_scroll = ttk.Scrollbar(tab2_outer, orient="vertical", command=tab2_canvas.yview)
    tab2 = ttk.Frame(tab2_canvas)
    tab2.bind("<Configure>", lambda e: tab2_canvas.configure(scrollregion=tab2_canvas.bbox("all")))
    tab2_canvas.create_window((0, 0), window=tab2, anchor="nw")
    tab2_canvas.configure(yscrollcommand=tab2_scroll.set)
    tab2_canvas.pack(side="left", fill="both", expand=True)
    tab2_scroll.pack(side="right", fill="y")

    _build_models_tab(tab2, values, ollama_models, combos)

    # Mouse wheel scrolling for both tabs
    def _on_mousewheel(event: tk.Event) -> None:  # type: ignore[type-arg]
        # Determine which canvas is visible
        current_tab = notebook.index(notebook.select())
        canvas = tab1_canvas if current_tab == 0 else tab2_canvas
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    dialog.bind_all("<MouseWheel>", _on_mousewheel)

    # ── Buttons ──
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill="x", padx=8, pady=8)

    def _on_save() -> None:
        nonlocal result
        collected: dict[str, str] = {}
        lang_codes = combos.pop("_lang_codes", None)
        for key, widget in combos.items():
            if isinstance(widget, tk.BooleanVar):
                collected[key] = "true" if widget.get() else "false"
            elif hasattr(widget, "get"):
                collected[key] = widget.get().strip()
        # Resolve language code from display label
        if lang_codes and "GUI_LANGUAGE" in collected:
            lang_label = collected["GUI_LANGUAGE"]
            langs = available_languages()
            for code, label in langs:
                if label == lang_label:
                    collected["GUI_LANGUAGE"] = code
                    break
        # Apply language change
        lang = collected.get("GUI_LANGUAGE", "")
        if lang:
            set_language(lang)
        result = collected
        dialog.unbind_all("<MouseWheel>")
        dialog.destroy()

    def _on_cancel() -> None:
        nonlocal result
        result = None
        dialog.unbind_all("<MouseWheel>")
        dialog.destroy()

    ttk.Button(btn_frame, text=t("setup.save"), command=_on_save).pack(side="right", padx=4)
    ttk.Button(btn_frame, text=t("setup.cancel"), command=_on_cancel).pack(side="right")

    dialog.protocol("WM_DELETE_WINDOW", _on_cancel)
    dialog.wait_window()

    return result
