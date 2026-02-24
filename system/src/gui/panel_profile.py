"""Profile dashboard panel for project-scoped extraction profiles."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from profile_engine.project_profiles import (
    clone_active_profile_to_file,
    get_active_profile_ref,
    load_active_profile_spec,
)


class ProfilePanel(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_configure_profile: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_root: Path | None = None
        self._on_configure_profile = on_configure_profile

        header = ttk.Frame(self)
        header.pack(fill="x", padx=4, pady=4)

        self._title_var = tk.StringVar(value="No active project")
        ttk.Label(
            header,
            textvariable=self._title_var,
            font=("MS Sans Serif", 9, "bold"),
        ).pack(side="left")

        ttk.Button(header, text="Refresh", command=self.refresh).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(header, text="Export YAML", command=self._export_profile_yaml).pack(
            side="right", padx=(6, 0)
        )
        self._configure_btn = ttk.Button(
            header,
            text="Configure...",
            command=self._open_configure_dialog,
        )
        self._configure_btn.pack(side="right", padx=(6, 0))

        summary = ttk.LabelFrame(self, text="Profile Summary", padding=8)
        summary.pack(fill="x", padx=4, pady=(0, 4))

        self._profile_id_var = tk.StringVar(value="-")
        self._profile_ver_var = tk.StringVar(value="-")
        self._profile_schema_var = tk.StringVar(value="-")
        self._profile_src_var = tk.StringVar(value="-")
        self._profile_fields_var = tk.StringVar(value="0")
        self._profile_rules_var = tk.StringVar(value="0")
        self._profile_quotes_var = tk.StringVar(value="-")
        self._profile_path_var = tk.StringVar(value="-")

        rows = [
            ("Profile ID", self._profile_id_var),
            ("Version", self._profile_ver_var),
            ("Schema", self._profile_schema_var),
            ("Source", self._profile_src_var),
            ("Fields", self._profile_fields_var),
            ("Rules", self._profile_rules_var),
            ("Quotes", self._profile_quotes_var),
            ("File", self._profile_path_var),
        ]
        for idx, (label, variable) in enumerate(rows):
            ttk.Label(summary, text=f"{label}:").grid(
                row=idx, column=0, sticky="w", padx=(0, 6), pady=1
            )
            ttk.Label(summary, textvariable=variable).grid(
                row=idx, column=1, sticky="w", pady=1
            )

        fields_box = ttk.LabelFrame(self, text="Fields", padding=4)
        fields_box.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        columns = ("field_id", "section", "type", "required")
        self._tree = ttk.Treeview(fields_box, columns=columns, show="headings", height=12)
        self._tree.heading("field_id", text="Field ID")
        self._tree.heading("section", text="Section")
        self._tree.heading("type", text="Type")
        self._tree.heading("required", text="Req")
        self._tree.column("field_id", width=250, anchor="w")
        self._tree.column("section", width=130, anchor="w")
        self._tree.column("type", width=120, anchor="w")
        self._tree.column("required", width=60, anchor="center")

        ybar = ttk.Scrollbar(fields_box, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=ybar.set)
        self._tree.pack(side="left", fill="both", expand=True)
        ybar.pack(side="right", fill="y")

    def set_project_root(self, project_root: Path | None) -> None:
        self._project_root = project_root.resolve() if project_root else None
        self.refresh()

    def set_configure_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_configure_profile = callback

    def refresh(self) -> None:
        self._tree.delete(*self._tree.get_children())
        if self._project_root is None:
            self._title_var.set("No active project")
            self._set_empty_summary()
            self._configure_btn.configure(state="disabled")
            return

        self._configure_btn.configure(state="normal")
        self._title_var.set(f"Project: {self._project_root.name}")

        ref = get_active_profile_ref(self._project_root)
        if ref is None:
            self._profile_id_var.set("(not configured)")
            self._profile_ver_var.set("-")
            self._profile_schema_var.set("-")
            self._profile_src_var.set("-")
            self._profile_fields_var.set("0")
            self._profile_rules_var.set("0")
            self._profile_quotes_var.set("-")
            self._profile_path_var.set("-")
            return

        self._profile_id_var.set(ref.profile_id)
        self._profile_ver_var.set(ref.version)
        self._profile_schema_var.set(ref.schema_version or "-")
        self._profile_src_var.set(ref.source)
        self._profile_path_var.set(str(ref.profile_path))

        try:
            spec, _loaded_ref = load_active_profile_spec(self._project_root)
        except Exception as exc:
            self._profile_fields_var.set("0")
            self._profile_rules_var.set("0")
            self._profile_quotes_var.set(f"error: {exc}")
            return

        self._profile_fields_var.set(str(len(spec.fields)))
        self._profile_rules_var.set(str(len(spec.rules)))
        if spec.quotes_policy.enabled:
            self._profile_quotes_var.set(
                f"{spec.quotes_policy.min_quotes}-{spec.quotes_policy.max_quotes}"
            )
        else:
            self._profile_quotes_var.set("disabled")

        for field in spec.fields:
            self._tree.insert(
                "",
                "end",
                values=(
                    field.field_id,
                    field.section,
                    field.field_type,
                    "Y" if field.required else "N",
                ),
            )

    def _set_empty_summary(self) -> None:
        self._profile_id_var.set("-")
        self._profile_ver_var.set("-")
        self._profile_schema_var.set("-")
        self._profile_src_var.set("-")
        self._profile_fields_var.set("0")
        self._profile_rules_var.set("0")
        self._profile_quotes_var.set("-")
        self._profile_path_var.set("-")

    def _open_configure_dialog(self) -> None:
        if self._on_configure_profile is None:
            return
        self._on_configure_profile()
        self.refresh()

    def _export_profile_yaml(self) -> None:
        if self._project_root is None:
            messagebox.showwarning(
                "Project required",
                "Select a project first.",
                parent=self,
            )
            return
        ref = get_active_profile_ref(self._project_root)
        if ref is None:
            messagebox.showwarning(
                "Profile required",
                "Configure a project profile first.",
                parent=self,
            )
            return

        default_name = f"{ref.profile_id}_{ref.version}.yaml"
        destination = filedialog.asksaveasfilename(
            parent=self,
            title="Export active profile YAML",
            defaultextension=".yaml",
            initialfile=default_name,
            filetypes=[("YAML", "*.yaml"), ("All files", "*.*")],
        )
        if not destination:
            return

        try:
            exported = clone_active_profile_to_file(
                self._project_root,
                Path(destination),
            )
        except Exception as exc:
            messagebox.showerror(
                "Export failed",
                f"Could not export profile.\n\nReason: {exc}",
                parent=self,
            )
            return

        messagebox.showinfo(
            "Export complete",
            f"Profile exported to:\n{exported}",
            parent=self,
        )
