"""Project profile setup dialog (GUI-first, YAML/XLSX optional, custom builder)."""

from __future__ import annotations

import re
import tkinter as tk
from datetime import UTC, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from profile_engine.models import ProfileRule, ProfileSpec
from profile_engine.project_profiles import (
    bootstrap_profile,
    build_universal_profile_prompt,
    export_profile_template_xlsx,
    get_active_profile_ref,
    import_profile_xlsx,
    import_profile_yaml,
    list_bundled_profiles,
    save_profile_version,
)
from profile_engine.validator import validate_rule_expressions

_FIELD_TYPES = ("string", "text", "int", "float", "bool", "enum", "list", "object")
_FIELD_SECTIONS = (
    "metadata",
    "context",
    "intervention",
    "mechanism",
    "outcome",
    "custom",
)
_RULE_SEVERITY = ("error", "warning")
_RULE_TRIGGER = ("always", "equals", "not_equals", "in_set", "regex", "not_empty")
_RULE_ASSERT = (
    "require_non_empty",
    "equals_value",
    "in_set",
    "contains_token",
    "custom_expr",
)


def _slugify(text: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "_" for ch in text.strip())
    while "__" in clean:
        clean = clean.replace("__", "_")
    return clean.strip("_") or "custom_profile"


def _default_custom_prompt(framework: str) -> str:
    fw = framework.strip() or "CUSTOM"
    return (
        f"# Universal Extraction Prompt ({fw})\n\n"
        "Objetivo: retornar somente YAML valido conforme o perfil ativo.\n\n"
        "Regras:\n"
        "- Use apenas campos do perfil ativo.\n"
        "- Nao invente valores sem evidencia textual.\n"
        "- Mantenha consistencia entre campos e regras.\n"
        "- Quando nao houver evidencia, use NR/empty conforme contrato do campo.\n"
        "- Quando houver quotes, use trechos literais com pagina/secao.\n"
        "- Nao inclua explicacoes fora do YAML.\n"
    )


def _single_quote_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _csv_tokens(text: str) -> list[str]:
    return [token.strip() for token in text.split(",") if token.strip()]


def _build_general_section(
    frame: ttk.Frame,
    *,
    active_line: str,
    mode_var: tk.StringVar,
) -> None:
    """Build header and mode selector for profile setup dialog."""
    ttk.Label(
        frame,
        text="Configure extraction profile for this project",
        font=("MS Sans Serif", 10, "bold"),
    ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
    ttk.Label(frame, text=active_line).grid(
        row=1,
        column=0,
        columnspan=4,
        sticky="w",
        pady=(0, 10),
    )

    selector = ttk.Frame(frame)
    selector.grid(row=2, column=0, columnspan=4, sticky="w", pady=(0, 8))
    ttk.Radiobutton(
        selector,
        text="Use preset profile",
        variable=mode_var,
        value="bundled",
    ).pack(side="left", padx=(0, 14))
    ttk.Radiobutton(
        selector,
        text="Import YAML",
        variable=mode_var,
        value="import",
    ).pack(side="left", padx=(0, 14))
    ttk.Radiobutton(
        selector,
        text="Import XLSX template",
        variable=mode_var,
        value="import_xlsx",
    ).pack(side="left", padx=(0, 14))
    ttk.Radiobutton(
        selector,
        text="Build custom profile (GUI)",
        variable=mode_var,
        value="custom",
    ).pack(side="left")


def _build_cimo_section(
    notebook: ttk.Notebook,
    *,
    bundles: list[str],
    bundle_var: tk.StringVar,
    yaml_var: tk.StringVar,
    prompt_var: tk.StringVar,
    xlsx_var: tk.StringVar,
    xlsx_prompt_var: tk.StringVar,
    on_browse_yaml: Callable[[], None],
    on_browse_prompt: Callable[[], None],
    on_browse_xlsx: Callable[[], None],
    on_browse_xlsx_prompt: Callable[[], None],
    on_download_template: Callable[[], None],
) -> tuple[ttk.Frame, ttk.Frame, ttk.Frame]:
    """Build preset/YAML/XLSX tabs used by standard CIMO flows."""
    bundled_tab = ttk.Frame(notebook, padding=10)
    notebook.add(bundled_tab, text="Preset Library")
    ttk.Label(bundled_tab, text="Profile:").grid(row=0, column=0, sticky="w")
    bundle_combo = ttk.Combobox(
        bundled_tab,
        textvariable=bundle_var,
        values=bundles,
        width=50,
        state="readonly" if bundles else "disabled",
    )
    bundle_combo.grid(row=0, column=1, sticky="ew")
    bundled_tab.columnconfigure(1, weight=1)

    import_tab = ttk.Frame(notebook, padding=10)
    notebook.add(import_tab, text="Import YAML")
    ttk.Label(import_tab, text="Profile YAML:").grid(row=0, column=0, sticky="w")
    yaml_entry = ttk.Entry(import_tab, textvariable=yaml_var, width=58)
    yaml_entry.grid(row=0, column=1, sticky="ew")
    ttk.Button(import_tab, text="Browse...", command=on_browse_yaml).grid(
        row=0, column=2, padx=(6, 0), sticky="w"
    )
    ttk.Label(import_tab, text="Optional prompt (.md):").grid(
        row=1, column=0, sticky="w", pady=(8, 0)
    )
    prompt_entry = ttk.Entry(import_tab, textvariable=prompt_var, width=58)
    prompt_entry.grid(row=1, column=1, sticky="ew", pady=(8, 0))
    ttk.Button(import_tab, text="Browse...", command=on_browse_prompt).grid(
        row=1, column=2, padx=(6, 0), sticky="w", pady=(8, 0)
    )
    ttk.Label(
        import_tab,
        text="If empty, the system applies the universal base prompt automatically.",
    ).grid(row=2, column=1, sticky="w", pady=(6, 0))
    import_tab.columnconfigure(1, weight=1)

    xlsx_tab = ttk.Frame(notebook, padding=10)
    notebook.add(xlsx_tab, text="Import XLSX")
    ttk.Label(xlsx_tab, text="Profile XLSX:").grid(row=0, column=0, sticky="w")
    ttk.Entry(xlsx_tab, textvariable=xlsx_var, width=58).grid(
        row=0, column=1, sticky="ew"
    )
    ttk.Button(xlsx_tab, text="Browse...", command=on_browse_xlsx).grid(
        row=0, column=2, padx=(6, 0), sticky="w"
    )
    ttk.Label(xlsx_tab, text="Optional prompt override (.md):").grid(
        row=1, column=0, sticky="w", pady=(8, 0)
    )
    ttk.Entry(xlsx_tab, textvariable=xlsx_prompt_var, width=58).grid(
        row=1, column=1, sticky="ew", pady=(8, 0)
    )
    ttk.Button(xlsx_tab, text="Browse...", command=on_browse_xlsx_prompt).grid(
        row=1, column=2, padx=(6, 0), sticky="w", pady=(8, 0)
    )
    ttk.Label(
        xlsx_tab,
        text="If empty, the system applies the universal base prompt automatically.",
    ).grid(row=2, column=1, sticky="w", pady=(6, 0))
    ttk.Button(
        xlsx_tab,
        text="Download XLSX Template...",
        command=on_download_template,
    ).grid(row=3, column=1, sticky="w", pady=(10, 0))
    xlsx_tab.columnconfigure(1, weight=1)
    return bundled_tab, import_tab, xlsx_tab


def _build_custom_spec_section(
    custom_tab: ttk.Frame,
    *,
    custom_id_var: tk.StringVar,
    custom_name_var: tk.StringVar,
    custom_framework_var: tk.StringVar,
    quote_min_var: tk.StringVar,
    quote_max_var: tk.StringVar,
    custom_fields: list[dict[str, object]],
    field_id_var: tk.StringVar,
    field_section_var: tk.StringVar,
    field_type_var: tk.StringVar,
    field_required_var: tk.BooleanVar,
    field_enum_var: tk.StringVar,
) -> tuple[ttk.Treeview, Callable[[], None], ttk.Button, ttk.Button]:
    """Build custom field summary section and return tree refresh callback."""
    ttk.Label(custom_tab, text="Profile ID:").grid(row=0, column=0, sticky="w")
    ttk.Entry(custom_tab, textvariable=custom_id_var, width=28).grid(
        row=0, column=1, sticky="ew", padx=(4, 8)
    )
    ttk.Label(custom_tab, text="Name:").grid(row=0, column=2, sticky="w")
    ttk.Entry(custom_tab, textvariable=custom_name_var, width=32).grid(
        row=0, column=3, sticky="ew", padx=(4, 0)
    )

    ttk.Label(custom_tab, text="Framework:").grid(row=1, column=0, sticky="w", pady=(6, 0))
    ttk.Entry(custom_tab, textvariable=custom_framework_var, width=20).grid(
        row=1, column=1, sticky="w", padx=(4, 8), pady=(6, 0)
    )
    ttk.Label(custom_tab, text="Quotes min/max:").grid(
        row=1, column=2, sticky="w", pady=(6, 0)
    )
    quote_frame = ttk.Frame(custom_tab)
    quote_frame.grid(row=1, column=3, sticky="w", pady=(6, 0))
    ttk.Entry(quote_frame, textvariable=quote_min_var, width=4).pack(side="left")
    ttk.Label(quote_frame, text="/").pack(side="left", padx=2)
    ttk.Entry(quote_frame, textvariable=quote_max_var, width=4).pack(side="left")

    columns = ("id", "section", "type", "required", "allowed")
    tree = ttk.Treeview(custom_tab, columns=columns, show="headings", height=9)
    tree.heading("id", text="Field ID")
    tree.heading("section", text="Section")
    tree.heading("type", text="Type")
    tree.heading("required", text="Req")
    tree.heading("allowed", text="Allowed Values")
    tree.column("id", width=160, anchor="w")
    tree.column("section", width=120, anchor="w")
    tree.column("type", width=90, anchor="w")
    tree.column("required", width=55, anchor="center")
    tree.column("allowed", width=260, anchor="w")
    tree.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=(8, 6))

    def _refresh_fields_tree() -> None:
        tree.delete(*tree.get_children())
        for item in custom_fields:
            allowed_values_raw = item.get("allowed_values", [])
            if not isinstance(allowed_values_raw, list):
                allowed_values_raw = []
            allowed = ", ".join(str(v) for v in allowed_values_raw)
            tree.insert(
                "",
                "end",
                values=(
                    item["id"],
                    item["section"],
                    item["type"],
                    "Y" if item.get("required") else "N",
                    allowed,
                ),
            )

    field_editor = ttk.Frame(custom_tab)
    field_editor.grid(row=3, column=0, columnspan=4, sticky="ew")
    ttk.Label(field_editor, text="Field ID").grid(row=0, column=0, sticky="w")
    ttk.Entry(field_editor, textvariable=field_id_var, width=18).grid(
        row=0, column=1, padx=(4, 8), sticky="w"
    )
    ttk.Label(field_editor, text="Section").grid(row=0, column=2, sticky="w")
    ttk.Combobox(
        field_editor,
        textvariable=field_section_var,
        values=_FIELD_SECTIONS,
        width=14,
        state="readonly",
    ).grid(row=0, column=3, padx=(4, 8), sticky="w")
    ttk.Label(field_editor, text="Type").grid(row=0, column=4, sticky="w")
    ttk.Combobox(
        field_editor,
        textvariable=field_type_var,
        values=_FIELD_TYPES,
        width=10,
        state="readonly",
    ).grid(row=0, column=5, padx=(4, 8), sticky="w")
    ttk.Checkbutton(field_editor, text="Required", variable=field_required_var).grid(
        row=0, column=6, sticky="w"
    )
    ttk.Label(field_editor, text="Enum values (comma)").grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(6, 0)
    )
    ttk.Entry(field_editor, textvariable=field_enum_var, width=52).grid(
        row=1, column=2, columnspan=4, padx=(4, 8), pady=(6, 0), sticky="ew"
    )

    action_row = ttk.Frame(custom_tab)
    action_row.grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 0))
    add_field_btn = ttk.Button(action_row, text="Add/Append Field")
    add_field_btn.pack(side="left")
    remove_field_btn = ttk.Button(action_row, text="Remove Selected")
    remove_field_btn.pack(side="left", padx=(6, 0))

    _refresh_fields_tree()
    return tree, _refresh_fields_tree, add_field_btn, remove_field_btn


def _build_validation_builder_section(
    custom_tab: ttk.Frame,
    *,
    field_choices: list[str],
    rule_id_var: tk.StringVar,
    rule_severity_var: tk.StringVar,
    rule_trigger_var: tk.StringVar,
    rule_trigger_field_var: tk.StringVar,
    rule_trigger_value_var: tk.StringVar,
    rule_assert_mode_var: tk.StringVar,
    rule_assert_field_var: tk.StringVar,
    rule_assert_value_var: tk.StringVar,
    rule_message_var: tk.StringVar,
) -> tuple[ttk.LabelFrame, ttk.Treeview, ttk.Combobox, ttk.Combobox, ttk.Button, ttk.Button]:
    """Build rule validation section and return key widgets."""
    rules_box = ttk.LabelFrame(custom_tab, text="Rule Builder", padding=6)
    rules_box.grid(row=5, column=0, columnspan=4, sticky="nsew", pady=(8, 0))

    rule_columns = ("id", "severity", "when", "assert", "message")
    rules_tree = ttk.Treeview(
        rules_box,
        columns=rule_columns,
        show="headings",
        height=5,
    )
    rules_tree.heading("id", text="Rule")
    rules_tree.heading("severity", text="Sev")
    rules_tree.heading("when", text="When")
    rules_tree.heading("assert", text="Assert")
    rules_tree.heading("message", text="Message")
    rules_tree.column("id", width=65, anchor="center")
    rules_tree.column("severity", width=65, anchor="center")
    rules_tree.column("when", width=200, anchor="w")
    rules_tree.column("assert", width=200, anchor="w")
    rules_tree.column("message", width=280, anchor="w")
    rules_tree.grid(row=0, column=0, columnspan=6, sticky="nsew")

    rules_scroll = ttk.Scrollbar(rules_box, orient="vertical", command=rules_tree.yview)
    rules_tree.configure(yscrollcommand=rules_scroll.set)
    rules_scroll.grid(row=0, column=6, sticky="ns")

    ttk.Label(rules_box, text="Rule ID").grid(row=1, column=0, sticky="w", pady=(6, 0))
    ttk.Entry(rules_box, textvariable=rule_id_var, width=8).grid(
        row=1, column=1, sticky="w", pady=(6, 0), padx=(4, 8)
    )
    ttk.Label(rules_box, text="Severity").grid(row=1, column=2, sticky="w", pady=(6, 0))
    ttk.Combobox(
        rules_box,
        textvariable=rule_severity_var,
        values=_RULE_SEVERITY,
        state="readonly",
        width=10,
    ).grid(row=1, column=3, sticky="w", pady=(6, 0), padx=(4, 8))
    ttk.Label(rules_box, text="Trigger").grid(row=1, column=4, sticky="w", pady=(6, 0))
    ttk.Combobox(
        rules_box,
        textvariable=rule_trigger_var,
        values=_RULE_TRIGGER,
        state="readonly",
        width=12,
    ).grid(row=1, column=5, sticky="w", pady=(6, 0), padx=(4, 0))

    ttk.Label(rules_box, text="Trigger field").grid(
        row=2, column=0, sticky="w", pady=(4, 0)
    )
    trigger_combo = ttk.Combobox(
        rules_box,
        textvariable=rule_trigger_field_var,
        values=field_choices,
        state="readonly",
        width=22,
    )
    trigger_combo.grid(row=2, column=1, columnspan=2, sticky="w", pady=(4, 0), padx=(4, 8))
    ttk.Label(rules_box, text="Trigger value/pattern").grid(
        row=2, column=3, sticky="w", pady=(4, 0)
    )
    ttk.Entry(rules_box, textvariable=rule_trigger_value_var, width=28).grid(
        row=2, column=4, columnspan=2, sticky="w", pady=(4, 0), padx=(4, 0)
    )

    ttk.Label(rules_box, text="Assert mode").grid(row=3, column=0, sticky="w", pady=(4, 0))
    ttk.Combobox(
        rules_box,
        textvariable=rule_assert_mode_var,
        values=_RULE_ASSERT,
        state="readonly",
        width=18,
    ).grid(row=3, column=1, sticky="w", pady=(4, 0), padx=(4, 8))
    ttk.Label(rules_box, text="Assert field").grid(row=3, column=2, sticky="w", pady=(4, 0))
    assert_combo = ttk.Combobox(
        rules_box,
        textvariable=rule_assert_field_var,
        values=field_choices,
        state="readonly",
        width=22,
    )
    assert_combo.grid(row=3, column=3, sticky="w", pady=(4, 0), padx=(4, 8))
    ttk.Label(rules_box, text="Assert value/expr").grid(
        row=3, column=4, sticky="w", pady=(4, 0)
    )
    ttk.Entry(rules_box, textvariable=rule_assert_value_var, width=28).grid(
        row=3, column=5, sticky="w", pady=(4, 0), padx=(4, 0)
    )

    ttk.Label(rules_box, text="Message").grid(row=4, column=0, sticky="w", pady=(4, 0))
    ttk.Entry(rules_box, textvariable=rule_message_var, width=92).grid(
        row=4, column=1, columnspan=5, sticky="ew", pady=(4, 0), padx=(4, 0)
    )

    rules_action_row = ttk.Frame(rules_box)
    rules_action_row.grid(row=5, column=0, columnspan=6, sticky="w", pady=(6, 0))
    add_rule_btn = ttk.Button(rules_action_row, text="Add Rule")
    add_rule_btn.pack(side="left")
    remove_rule_btn = ttk.Button(rules_action_row, text="Remove Selected Rule")
    remove_rule_btn.pack(side="left", padx=(6, 0))
    return rules_box, rules_tree, trigger_combo, assert_combo, add_rule_btn, remove_rule_btn


def _build_validation_section(frame: ttk.Frame, validation_var: tk.StringVar) -> tk.Label:
    """Build validation status line below tabs."""
    validation_label = tk.Label(
        frame,
        textvariable=validation_var,
        anchor="w",
        justify="left",
        bg="#C0C0C0",
        fg="#8B0000",
        wraplength=820,
    )
    validation_label.grid(
        row=4,
        column=0,
        columnspan=4,
        sticky="ew",
        pady=(10, 0),
    )
    return validation_label


def _build_preview_section(
    frame: ttk.Frame,
    *,
    on_save: Callable[[], None],
    on_cancel: Callable[[], None],
) -> ttk.Button:
    """Build footer action buttons and return save button."""
    button_row = ttk.Frame(frame)
    button_row.grid(row=5, column=0, columnspan=4, sticky="e", pady=(12, 0))
    save_button = ttk.Button(button_row, text="Save", command=on_save)
    save_button.pack(side="left", padx=(0, 6))
    ttk.Button(button_row, text="Cancel", command=on_cancel).pack(side="left")
    return save_button


def _build_custom_prompt_section(
    custom_tab: ttk.Frame, *, custom_framework_var: tk.StringVar
) -> tk.Text:
    """Build inline prompt editor for custom profile mode."""
    prompt_box = ttk.LabelFrame(custom_tab, text="Profile Prompt (inline)", padding=6)
    prompt_box.grid(row=6, column=0, columnspan=4, sticky="nsew", pady=(8, 0))
    custom_prompt_text = tk.Text(
        prompt_box,
        height=8,
        wrap="word",
        font=("Consolas", 9),
    )
    custom_prompt_text.pack(side="left", fill="both", expand=True)
    custom_prompt_scroll = ttk.Scrollbar(
        prompt_box,
        orient="vertical",
        command=custom_prompt_text.yview,
    )
    custom_prompt_scroll.pack(side="right", fill="y")
    custom_prompt_text.configure(yscrollcommand=custom_prompt_scroll.set)
    custom_prompt_text.insert("1.0", _default_custom_prompt(custom_framework_var.get()))
    return custom_prompt_text


def _center_dialog_on_parent(dialog: tk.Toplevel, parent: tk.Misc) -> None:
    """Center dialog relative to parent window geometry."""
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    px = parent.winfo_rootx() if isinstance(parent, (tk.Tk, tk.Toplevel)) else 100
    py = parent.winfo_rooty() if isinstance(parent, (tk.Tk, tk.Toplevel)) else 100
    pw = parent.winfo_width() if isinstance(parent, (tk.Tk, tk.Toplevel)) else 1000
    ph = parent.winfo_height() if isinstance(parent, (tk.Tk, tk.Toplevel)) else 700
    x = px + max((pw - width) // 2, 10)
    y = py + max((ph - height) // 2, 10)
    dialog.geometry(f"+{x}+{y}")


def prompt_project_profile_setup(parent: tk.Misc, project_root: Path) -> bool:
    """Configure or import project profile.

    Returns True when profile activation succeeded.
    """
    root = Path(project_root).resolve()
    bundles = list_bundled_profiles()
    active = get_active_profile_ref(root)

    def _initial_mode_and_bundle() -> tuple[str, str]:
        """Choose startup mode from active profile source (no hardcoded preset bias)."""
        default_bundle = bundles[0] if bundles else ""
        if active is None:
            return "custom", default_bundle

        source = str(active.source or "").strip().lower()
        profile_id = str(active.profile_id or "").strip()
        if profile_id in bundles and source.startswith("bundled:"):
            return "bundled", profile_id
        if source == "yaml_import":
            return "import", default_bundle
        if source == "xlsx_import":
            return "import_xlsx", default_bundle
        if profile_id in bundles:
            return "bundled", profile_id
        return "custom", default_bundle

    initial_mode, initial_bundle = _initial_mode_and_bundle()

    dialog = tk.Toplevel(parent)
    dialog.title("Project Profile Setup")
    dialog.configure(bg="#C0C0C0")
    dialog.resizable(True, True)
    dialog.minsize(880, 620)
    if isinstance(parent, (tk.Tk, tk.Toplevel)):
        dialog.transient(parent)
    dialog.grab_set()

    result = {"ok": False}
    mode_var = tk.StringVar(value=initial_mode)
    bundle_var = tk.StringVar(value=initial_bundle)
    yaml_var = tk.StringVar(value="")
    prompt_var = tk.StringVar(value="")
    xlsx_var = tk.StringVar(value="")
    xlsx_prompt_var = tk.StringVar(value="")
    validation_var = tk.StringVar(value="")

    # Custom mode vars
    custom_id_var = tk.StringVar(value="custom_rsl_profile")
    custom_name_var = tk.StringVar(value="Custom RSL Profile")
    custom_framework_var = tk.StringVar(value="CUSTOM")
    quote_min_var = tk.StringVar(value="3")
    quote_max_var = tk.StringVar(value="8")

    field_id_var = tk.StringVar(value="")
    field_section_var = tk.StringVar(value="custom")
    field_type_var = tk.StringVar(value="string")
    field_required_var = tk.BooleanVar(value=True)
    field_enum_var = tk.StringVar(value="")
    rule_id_var = tk.StringVar(value="R1")
    rule_severity_var = tk.StringVar(value="error")
    rule_trigger_var = tk.StringVar(value="always")
    rule_trigger_field_var = tk.StringVar(value="ArtigoID")
    rule_trigger_value_var = tk.StringVar(value="")
    rule_assert_mode_var = tk.StringVar(value="require_non_empty")
    rule_assert_field_var = tk.StringVar(value="ArtigoID")
    rule_assert_value_var = tk.StringVar(value="")
    rule_message_var = tk.StringVar(value="Rule validation failed.")

    custom_fields: list[dict[str, object]] = [
        {
            "id": "ArtigoID",
            "section": "metadata",
            "type": "string",
            "required": True,
            "allowed_values": [],
        }
    ]
    custom_rules: list[dict[str, str]] = []

    frame = ttk.Frame(dialog, padding=12)
    frame.pack(fill="both", expand=True)

    if active is not None:
        active_line = f"Active: {active.profile_id} v{active.version}"
    else:
        active_line = "Active: none (required before running pipeline)"
    _build_general_section(frame, active_line=active_line, mode_var=mode_var)

    notebook = ttk.Notebook(frame)
    notebook.grid(row=3, column=0, columnspan=4, sticky="nsew")
    mode_to_tab: dict[str, ttk.Frame] = {}

    def _browse_yaml() -> None:
        selected = filedialog.askopenfilename(
            parent=dialog,
            title="Select profile YAML",
            filetypes=[("YAML", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if selected:
            yaml_var.set(selected)
            mode_var.set("import")
            target = mode_to_tab.get("import")
            if target is not None:
                notebook.select(target)

    def _browse_prompt() -> None:
        selected = filedialog.askopenfilename(
            parent=dialog,
            title="Select extract prompt markdown",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt"), ("All files", "*.*")],
        )
        if selected:
            prompt_var.set(selected)

    def _browse_xlsx() -> None:
        selected = filedialog.askopenfilename(
            parent=dialog,
            title="Select profile XLSX template",
            filetypes=[("Excel", "*.xlsx"), ("All files", "*.*")],
        )
        if selected:
            xlsx_var.set(selected)
            mode_var.set("import_xlsx")
            target = mode_to_tab.get("import_xlsx")
            if target is not None:
                notebook.select(target)

    def _browse_xlsx_prompt() -> None:
        selected = filedialog.askopenfilename(
            parent=dialog,
            title="Select custom extract prompt markdown",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt"), ("All files", "*.*")],
        )
        if selected:
            xlsx_prompt_var.set(selected)

    def _download_xlsx_template() -> None:
        destination = filedialog.asksaveasfilename(
            parent=dialog,
            title="Save profile XLSX template",
            defaultextension=".xlsx",
            initialfile="profile_template.xlsx",
            filetypes=[("Excel", "*.xlsx"), ("All files", "*.*")],
        )
        if not destination:
            return
        try:
            exported = export_profile_template_xlsx(Path(destination))
        except Exception as exc:
            messagebox.showerror(
                "Template export failed",
                f"Could not create XLSX template.\n\nReason: {exc}",
                parent=dialog,
            )
            return
        messagebox.showinfo(
            "Template ready",
            f"XLSX template saved to:\n{exported}",
            parent=dialog,
        )

    bundled_tab, import_tab, xlsx_tab = _build_cimo_section(
        notebook,
        bundles=bundles,
        bundle_var=bundle_var,
        yaml_var=yaml_var,
        prompt_var=prompt_var,
        xlsx_var=xlsx_var,
        xlsx_prompt_var=xlsx_prompt_var,
        on_browse_yaml=_browse_yaml,
        on_browse_prompt=_browse_prompt,
        on_browse_xlsx=_browse_xlsx,
        on_browse_xlsx_prompt=_browse_xlsx_prompt,
        on_download_template=_download_xlsx_template,
    )

    custom_tab = ttk.Frame(notebook, padding=10)
    notebook.add(custom_tab, text="Custom Builder")

    mode_to_tab.update(
        {
            "bundled": bundled_tab,
            "import": import_tab,
            "import_xlsx": xlsx_tab,
            "custom": custom_tab,
        }
    )
    tab_to_mode = {str(tab): mode for mode, tab in mode_to_tab.items()}

    def _sync_mode_to_tab(*_args) -> None:
        target = mode_to_tab.get(mode_var.get(), custom_tab)
        try:
            notebook.select(target)
        except tk.TclError:
            return

    def _sync_tab_to_mode(_event: object | None = None) -> None:
        try:
            selected = str(notebook.select())
        except tk.TclError:
            return
        mapped = tab_to_mode.get(selected)
        if mapped and mode_var.get() != mapped:
            mode_var.set(mapped)

    notebook.bind("<<NotebookTabChanged>>", _sync_tab_to_mode)
    mode_var.trace_add("write", _sync_mode_to_tab)

    tree, _refresh_fields_tree, add_field_button, remove_field_button = _build_custom_spec_section(
        custom_tab,
        custom_id_var=custom_id_var,
        custom_name_var=custom_name_var,
        custom_framework_var=custom_framework_var,
        quote_min_var=quote_min_var,
        quote_max_var=quote_max_var,
        custom_fields=custom_fields,
        field_id_var=field_id_var,
        field_section_var=field_section_var,
        field_type_var=field_type_var,
        field_required_var=field_required_var,
        field_enum_var=field_enum_var,
    )

    def _add_field() -> None:
        field_id = field_id_var.get().strip()
        if not field_id:
            messagebox.showwarning("Missing field ID", "Enter field ID.", parent=dialog)
            return
        for existing in custom_fields:
            if str(existing["id"]) == field_id:
                messagebox.showwarning(
                    "Duplicate field",
                    f"Field '{field_id}' already exists.",
                    parent=dialog,
                )
                return
        enum_values = [
            token.strip()
            for token in field_enum_var.get().split(",")
            if token.strip()
        ]
        custom_fields.append(
            {
                "id": field_id,
                "section": field_section_var.get().strip() or "custom",
                "type": field_type_var.get().strip() or "string",
                "required": bool(field_required_var.get()),
                "allowed_values": enum_values,
            }
        )
        field_id_var.set("")
        field_enum_var.set("")
        field_type_var.set("string")
        field_required_var.set(True)
        _refresh_fields_tree()
        _refresh_field_choices()
        _update_save_state()
        mode_var.set("custom")
        notebook.select(custom_tab)

    def _remove_selected_field() -> None:
        selected = tree.selection()
        if not selected:
            return
        selected_values = tree.item(selected[0], "values")
        target_id = str(selected_values[0])
        custom_fields[:] = [f for f in custom_fields if str(f["id"]) != target_id]
        token = f"get('{_single_quote_escape(target_id)}')"
        custom_rules[:] = [
            rule
            for rule in custom_rules
            if token not in str(rule.get("when", ""))
            and token not in str(rule.get("assert", ""))
        ]
        _refresh_fields_tree()
        _refresh_field_choices()
        _refresh_rules_tree()
        _update_save_state()

    add_field_button.configure(command=_add_field)
    remove_field_button.configure(command=_remove_selected_field)

    field_choices = [str(item["id"]) for item in custom_fields]
    (
        rules_box,
        rules_tree,
        trigger_combo,
        assert_combo,
        add_rule_button,
        remove_rule_button,
    ) = _build_validation_builder_section(
        custom_tab,
        field_choices=field_choices,
        rule_id_var=rule_id_var,
        rule_severity_var=rule_severity_var,
        rule_trigger_var=rule_trigger_var,
        rule_trigger_field_var=rule_trigger_field_var,
        rule_trigger_value_var=rule_trigger_value_var,
        rule_assert_mode_var=rule_assert_mode_var,
        rule_assert_field_var=rule_assert_field_var,
        rule_assert_value_var=rule_assert_value_var,
        rule_message_var=rule_message_var,
    )

    def _refresh_rules_tree() -> None:
        rules_tree.delete(*rules_tree.get_children())
        for item in custom_rules:
            rules_tree.insert(
                "",
                "end",
                values=(
                    item.get("id", ""),
                    item.get("severity", ""),
                    item.get("when", ""),
                    item.get("assert", ""),
                    item.get("message", ""),
                ),
            )

    def _refresh_field_choices() -> None:
        nonlocal field_choices
        field_choices = [str(item["id"]) for item in custom_fields]
        trigger_combo.configure(values=field_choices)
        assert_combo.configure(values=field_choices)
        if field_choices:
            if rule_trigger_field_var.get() not in field_choices:
                rule_trigger_field_var.set(field_choices[0])
            if rule_assert_field_var.get() not in field_choices:
                rule_assert_field_var.set(field_choices[0])

    def _build_when_expr() -> str:
        mode = rule_trigger_var.get().strip() or "always"
        field_name = _single_quote_escape(rule_trigger_field_var.get().strip())
        value = _single_quote_escape(rule_trigger_value_var.get().strip())
        if mode == "always":
            return "True"
        if not field_name:
            raise ValueError("Trigger field is required.")
        if mode == "equals":
            return f"eq(get('{field_name}'), '{value}')"
        if mode == "not_equals":
            return f"ne(get('{field_name}'), '{value}')"
        if mode == "in_set":
            tokens = _csv_tokens(rule_trigger_value_var.get())
            token_expr = ", ".join(f"'{_single_quote_escape(t)}'" for t in tokens)
            return f"in_set(get('{field_name}'), [{token_expr}])"
        if mode == "regex":
            return f"regex(get('{field_name}'), '{value}')"
        if mode == "not_empty":
            return f"not_empty(get('{field_name}'))"
        raise ValueError(f"Unsupported trigger mode: {mode}")

    def _build_assert_expr() -> str:
        mode = rule_assert_mode_var.get().strip() or "require_non_empty"
        field_name = _single_quote_escape(rule_assert_field_var.get().strip())
        value = _single_quote_escape(rule_assert_value_var.get().strip())
        if mode != "custom_expr" and not field_name:
            raise ValueError("Assert field is required.")
        if mode == "require_non_empty":
            return f"not_empty(get('{field_name}'))"
        if mode == "equals_value":
            return f"eq(get('{field_name}'), '{value}')"
        if mode == "in_set":
            tokens = _csv_tokens(rule_assert_value_var.get())
            token_expr = ", ".join(f"'{_single_quote_escape(t)}'" for t in tokens)
            return f"in_set(get('{field_name}'), [{token_expr}])"
        if mode == "contains_token":
            return f"contains(get('{field_name}'), '{value}')"
        if mode == "custom_expr":
            expr = rule_assert_value_var.get().strip()
            if not expr:
                raise ValueError("Assert custom expression is required.")
            return expr
        raise ValueError(f"Unsupported assert mode: {mode}")

    def _next_rule_id() -> str:
        return f"R{len(custom_rules) + 1}"

    def _add_rule() -> None:
        rule_id = rule_id_var.get().strip() or _next_rule_id()
        for existing in custom_rules:
            if existing.get("id") == rule_id:
                messagebox.showwarning(
                    "Duplicate rule",
                    f"Rule '{rule_id}' already exists.",
                    parent=dialog,
                )
                return
        try:
            when_expr = _build_when_expr()
            assert_expr = _build_assert_expr()
        except ValueError as exc:
            messagebox.showwarning(
                "Invalid rule",
                str(exc),
                parent=dialog,
            )
            return
        message = rule_message_var.get().strip() or "Rule validation failed."
        custom_rules.append(
            {
                "id": rule_id,
                "severity": rule_severity_var.get().strip() or "error",
                "when": when_expr,
                "assert": assert_expr,
                "message": message,
            }
        )
        rule_id_var.set(_next_rule_id())
        rule_trigger_value_var.set("")
        rule_assert_value_var.set("")
        rule_message_var.set("Rule validation failed.")
        _refresh_rules_tree()
        _update_save_state()
        mode_var.set("custom")
        notebook.select(custom_tab)

    def _remove_selected_rule() -> None:
        selected = rules_tree.selection()
        if not selected:
            return
        values = rules_tree.item(selected[0], "values")
        target = str(values[0])
        custom_rules[:] = [r for r in custom_rules if r.get("id") != target]
        _refresh_rules_tree()
        _update_save_state()

    add_rule_button.configure(command=_add_rule)
    remove_rule_button.configure(command=_remove_selected_rule)
    _refresh_field_choices()

    custom_prompt_text = _build_custom_prompt_section(
        custom_tab,
        custom_framework_var=custom_framework_var,
    )

    def _extract_expr_fields(expr: str) -> set[str]:
        return set(re.findall(r"get\('([^']+)'\)", expr or ""))

    def _validate_custom_builder() -> list[str]:
        issues: list[str] = []
        raw_profile_id = custom_id_var.get().strip()
        profile_name = custom_name_var.get().strip()
        if not raw_profile_id:
            issues.append("Profile ID is required in Custom Builder.")
        if not profile_name:
            issues.append("Profile name is required in Custom Builder.")

        try:
            min_quotes = int(quote_min_var.get().strip() or "3")
            max_quotes = int(quote_max_var.get().strip() or "8")
        except ValueError:
            issues.append("Quotes min/max must be valid integers.")
        else:
            if min_quotes < 0:
                issues.append("Quotes min must be >= 0.")
            if max_quotes < min_quotes:
                issues.append("Quotes max must be >= min.")

        if not custom_fields:
            issues.append("At least one field is required.")
            return issues

        seen_fields: set[str] = set()
        for field_item in custom_fields:
            field_id = str(field_item.get("id", "")).strip()
            field_type = str(field_item.get("type", "string")).strip()
            allowed_values = field_item.get("allowed_values", [])
            if not field_id:
                issues.append("Field ID cannot be empty.")
                continue
            if field_id in seen_fields:
                issues.append(f"Duplicate field ID: {field_id}")
            seen_fields.add(field_id)
            if field_type not in _FIELD_TYPES:
                issues.append(f"Field '{field_id}' has invalid type '{field_type}'.")
            if field_type == "enum" and not allowed_values:
                issues.append(f"Field '{field_id}' is enum and requires allowed values.")

        if "ArtigoID" not in seen_fields:
            issues.append("Field 'ArtigoID' is required for pipeline mapping.")

        seen_rule_ids: set[str] = set()
        rule_models: list[ProfileRule] = []
        for rule in custom_rules:
            rule_id = str(rule.get("id", "")).strip()
            severity = str(rule.get("severity", "")).strip()
            when_expr = str(rule.get("when", "")).strip()
            assert_expr = str(rule.get("assert", "")).strip()
            if not rule_id:
                issues.append("Rule ID cannot be empty.")
                continue
            if rule_id in seen_rule_ids:
                issues.append(f"Duplicate rule ID: {rule_id}")
            seen_rule_ids.add(rule_id)
            if severity not in _RULE_SEVERITY:
                issues.append(
                    f"Rule '{rule_id}' has invalid severity '{severity}'."
                )
            if not when_expr:
                issues.append(f"Rule '{rule_id}' requires a trigger expression.")
            if not assert_expr:
                issues.append(f"Rule '{rule_id}' requires an assert expression.")

            for referenced in _extract_expr_fields(when_expr) | _extract_expr_fields(assert_expr):
                if referenced not in seen_fields:
                    issues.append(
                        f"Rule '{rule_id}' references unknown field '{referenced}'."
                    )

            rule_models.append(
                ProfileRule.from_dict(
                    {
                        "id": rule_id,
                        "severity": severity or "error",
                        "when": when_expr or "True",
                        "assert": assert_expr or "True",
                        "message": str(rule.get("message", "")).strip()
                        or "Rule validation failed.",
                    }
                )
            )

        issues.extend(validate_rule_expressions(tuple(rule_models)))
        return issues

    def _current_mode_issues() -> list[str]:
        selected_mode = mode_var.get()
        if selected_mode == "bundled":
            profile_id = bundle_var.get().strip()
            if not bundles:
                return ["No preset profiles available."]
            if not profile_id:
                return ["Select one preset profile."]
            if profile_id not in bundles:
                return [f"Preset profile '{profile_id}' is not available."]
            return []
        if selected_mode == "import":
            path_text = yaml_var.get().strip()
            if not path_text:
                return ["Select one YAML file to import."]
            candidate = Path(path_text)
            if candidate.suffix.lower() not in {".yaml", ".yml"}:
                return ["Imported profile file must be .yaml or .yml."]
            if not candidate.exists():
                return ["Selected YAML file does not exist."]
            prompt_text = prompt_var.get().strip()
            if prompt_text and not Path(prompt_text).exists():
                return ["Selected prompt file does not exist."]
            return []
        if selected_mode == "import_xlsx":
            path_text = xlsx_var.get().strip()
            if not path_text:
                return ["Select one XLSX template file to import."]
            candidate = Path(path_text)
            if candidate.suffix.lower() != ".xlsx":
                return ["Imported profile file must be .xlsx."]
            if not candidate.exists():
                return ["Selected XLSX file does not exist."]
            prompt_text = xlsx_prompt_var.get().strip()
            if prompt_text and not Path(prompt_text).exists():
                return ["Selected prompt override file does not exist."]
            return []
        return _validate_custom_builder()

    save_button: ttk.Button | None = None

    def _render_validation_message(issues: list[str]) -> None:
        if not issues:
            validation_var.set("Configuration looks valid.")
            return
        preview = issues[:3]
        suffix = " ..." if len(issues) > 3 else ""
        validation_var.set(f"{len(issues)} issue(s): " + " | ".join(preview) + suffix)

    def _update_save_state(*_args) -> None:
        issues = _current_mode_issues()
        _render_validation_message(issues)
        if save_button is not None:
            save_button.configure(state="normal" if not issues else "disabled")

    custom_tab.columnconfigure(1, weight=1)
    custom_tab.columnconfigure(3, weight=1)
    custom_tab.rowconfigure(2, weight=1)
    custom_tab.rowconfigure(5, weight=1)
    custom_tab.rowconfigure(6, weight=1)
    rules_box.columnconfigure(5, weight=1)
    rules_box.rowconfigure(0, weight=1)

    _build_validation_section(frame, validation_var)

    def _build_custom_spec() -> tuple[ProfileSpec, str]:
        profile_id = _slugify(custom_id_var.get())
        profile_name = custom_name_var.get().strip() or profile_id
        framework = custom_framework_var.get().strip() or "CUSTOM"
        min_quotes = int(quote_min_var.get().strip() or "3")
        max_quotes = int(quote_max_var.get().strip() or "8")
        if min_quotes < 0 or max_quotes < min_quotes:
            raise ValueError("Invalid quote min/max values.")

        if not custom_fields:
            raise ValueError("Add at least one field in Custom Builder.")

        fields_payload: list[dict[str, object]] = []
        for item in custom_fields:
            field_id = str(item.get("id", "")).strip()
            field_type = str(item.get("type", "string")).strip()
            allowed_values = item.get("allowed_values", [])
            payload = {
                "id": field_id,
                "label": field_id,
                "section": str(item.get("section", "custom")).strip() or "custom",
                "type": field_type,
                "required": bool(item.get("required", True)),
                "allowed_values": allowed_values if isinstance(allowed_values, list) else [],
            }
            fields_payload.append(payload)

        profile_payload = {
            "profile": {
                "meta": {
                    "profile_id": profile_id,
                    "version": datetime.now(UTC).strftime("%Y.%m.%d.%H%M%S"),
                    "name": profile_name,
                    "framework": framework,
                    "language": "pt-BR",
                    "description": "Created via GUI custom builder",
                },
                "fields": fields_payload,
                "rules": custom_rules,
                "quotes_policy": {
                    "enabled": True,
                    "min_quotes": min_quotes,
                    "max_quotes": max_quotes,
                    "required_types": [],
                    "allowed_types": ["Outro"],
                    "quote_schema": {
                        "id_pattern": "^Q\\d{3}$",
                        "required_fields": ["QuoteID", "TipoQuote", "Trecho", "Página"],
                        "trecho_min_length": 10,
                    },
                },
                "output": {
                    "format": "yaml",
                    "enforce_field_names": True,
                    "include_sections": True,
                },
                "prompt_contract": {
                    "return_only_output": True,
                    "include_self_review": True,
                    "instructions": [
                        "Retorne somente YAML.",
                        "Use apenas campos declarados no perfil ativo.",
                    ],
                },
            }
        }
        spec = ProfileSpec.from_dict(profile_payload)
        errors = spec.validate_structure()
        errors.extend(validate_rule_expressions(spec.rules))
        if errors:
            raise ValueError("; ".join(errors))
        prompt_override = custom_prompt_text.get("1.0", "end").strip()
        if not prompt_override:
            prompt_override = build_universal_profile_prompt(spec)
        return spec, prompt_override

    def _save() -> None:
        try:
            issues = _current_mode_issues()
            if issues:
                raise ValueError(
                    "Fix profile configuration issues before saving: "
                    + "; ".join(issues[:5])
                )
            selected_mode = mode_var.get()
            if selected_mode == "bundled":
                profile_id = bundle_var.get().strip()
                if not profile_id:
                    raise ValueError("Select a preset profile.")
                ref = bootstrap_profile(root, profile_id=profile_id, activate=True)
            elif selected_mode == "import":
                yaml_path = Path(yaml_var.get().strip())
                if not yaml_path.exists():
                    raise ValueError("Select a valid profile YAML file.")
                prompt_path = None
                prompt_text = prompt_var.get().strip()
                if prompt_text:
                    candidate = Path(prompt_text)
                    if not candidate.exists():
                        raise ValueError("Selected prompt file does not exist.")
                    prompt_path = candidate
                ref = import_profile_yaml(
                    root,
                    yaml_path=yaml_path,
                    prompt_path=prompt_path,
                    activate=True,
                )
            elif selected_mode == "import_xlsx":
                xlsx_path = Path(xlsx_var.get().strip())
                if not xlsx_path.exists():
                    raise ValueError("Select a valid profile XLSX file.")
                prompt_path = None
                prompt_text = xlsx_prompt_var.get().strip()
                if prompt_text:
                    candidate = Path(prompt_text)
                    if not candidate.exists():
                        raise ValueError("Selected prompt override does not exist.")
                    prompt_path = candidate
                ref = import_profile_xlsx(
                    root,
                    xlsx_path=xlsx_path,
                    prompt_path=prompt_path,
                    activate=True,
                )
            else:
                spec, generated_prompt = _build_custom_spec()
                ref = save_profile_version(
                    root,
                    spec=spec,
                    prompt_text=generated_prompt,
                    activate=True,
                    source="gui_custom_builder",
                )

            messagebox.showinfo(
                "Profile configured",
                f"Active profile: {ref.profile_id} v{ref.version}",
                parent=dialog,
            )
            result["ok"] = True
            dialog.destroy()
        except Exception as exc:
            messagebox.showerror(
                "Profile setup failed",
                (
                    "Could not activate profile.\n\n"
                    f"Reason: {exc}\n\n"
                    "Review the configuration summary and correct invalid fields/rules."
                ),
                parent=dialog,
            )

    def _cancel() -> None:
        dialog.destroy()

    save_button = _build_preview_section(frame, on_save=_save, on_cancel=_cancel)

    frame.columnconfigure(1, weight=1)
    frame.columnconfigure(2, weight=1)
    frame.columnconfigure(3, weight=1)
    frame.rowconfigure(3, weight=1)

    for variable in (
        mode_var,
        bundle_var,
        yaml_var,
        prompt_var,
        xlsx_var,
        xlsx_prompt_var,
        custom_id_var,
        custom_name_var,
        custom_framework_var,
        quote_min_var,
        quote_max_var,
        rule_id_var,
        rule_trigger_var,
        rule_trigger_field_var,
        rule_trigger_value_var,
        rule_assert_mode_var,
        rule_assert_field_var,
        rule_assert_value_var,
        rule_message_var,
    ):
        variable.trace_add("write", _update_save_state)
    _sync_mode_to_tab()
    _update_save_state()

    _center_dialog_on_parent(dialog, parent)
    dialog.wait_window()

    return bool(result["ok"])
