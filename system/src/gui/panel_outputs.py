"""Output explorer panel with filtering, sorting, context menu, and YAML preview."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from gui.panel_yaml_preview import YAMLPreviewPanel
from gui.tooltip import add_tooltip
from gui.i18n import t


@dataclass(frozen=True)
class OutputEntry:
    path: Path
    file_type: str
    size: int
    modified: float


class OutputsPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self._project_root: Path | None = None
        self._entries: list[OutputEntry] = []
        self._filtered: list[OutputEntry] = []
        self._row_entry_by_iid: dict[str, OutputEntry] = {}

        self._filter_type_var = tk.StringVar(value="All")
        self._filter_text_var = tk.StringVar(value="")
        self._sort_column = "name"
        self._sort_desc = False

        self._icons = self._build_icons()

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=4, pady=4)

        refresh_button = ttk.Button(toolbar, text=t("outputs.refresh"), command=self.refresh)
        refresh_button.pack(side="left")
        open_button = ttk.Button(toolbar, text=t("outputs.open"), command=self.open_selected)
        open_button.pack(
            side="left", padx=(4, 0)
        )
        copy_button = ttk.Button(toolbar, text=t("outputs.copy_path"), command=self.copy_selected)
        copy_button.pack(
            side="left", padx=(4, 0)
        )

        ttk.Label(toolbar, text=t("outputs.type_filter")).pack(side="left", padx=(14, 4))
        type_combo = ttk.Combobox(
            toolbar,
            textvariable=self._filter_type_var,
            values=["All", "YAML", "Logs", "Consolidated", "PDF", "CSV"],
            width=12,
            state="readonly",
        )
        type_combo.pack(side="left")
        type_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_filter())

        ttk.Label(toolbar, text=t("outputs.find")).pack(side="left", padx=(10, 4))
        find_entry = ttk.Entry(toolbar, textvariable=self._filter_text_var, width=24)
        find_entry.pack(side="left")
        find_entry.bind("<KeyRelease>", lambda _e: self._apply_filter())

        add_tooltip(refresh_button, t("outputs.tooltip.refresh"))
        add_tooltip(open_button, t("outputs.tooltip.open"))
        add_tooltip(copy_button, t("outputs.tooltip.copy_path"))
        add_tooltip(type_combo, t("outputs.tooltip.type_filter"))
        add_tooltip(find_entry, t("outputs.tooltip.find"))

        split = ttk.Panedwindow(self, orient="vertical")
        split.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        list_frame = ttk.Frame(split)
        preview_frame = ttk.Frame(split)
        split.add(list_frame, weight=3)
        split.add(preview_frame, weight=2)

        columns = ("name", "type", "size", "modified")
        self._tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="tree headings",
            height=12,
        )
        self._tree.heading("name", text=t("outputs.col_name"), command=lambda: self._sort_by("name"))
        self._tree.heading("type", text=t("outputs.col_type"), command=lambda: self._sort_by("type"))
        self._tree.heading("size", text=t("outputs.col_size"), command=lambda: self._sort_by("size"))
        self._tree.heading(
            "modified",
            text=t("outputs.col_modified"),
            command=lambda: self._sort_by("modified"),
        )

        self._tree.column("#0", width=24, anchor="center")
        self._tree.column("name", width=360, anchor="w")
        self._tree.column("type", width=110, anchor="w")
        self._tree.column("size", width=80, anchor="e")
        self._tree.column("modified", width=140, anchor="w")

        ybar = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=ybar.set)
        self._tree.pack(side="left", fill="both", expand=True)
        ybar.pack(side="right", fill="y")

        self._preview = YAMLPreviewPanel(preview_frame)
        self._preview.pack(fill="both", expand=True)
        self._preview.clear()

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        self._menu_item = tk.Menu(self, tearoff=False)
        self._menu_item.add_command(label=t("outputs.open"), command=self.open_selected)
        self._menu_item.add_command(label=t("outputs.open_folder"), command=self.open_selected_folder)
        self._menu_item.add_command(label=t("outputs.copy_path"), command=self.copy_selected)
        self._menu_item.add_separator()
        self._menu_item.add_command(label=t("outputs.delete"), command=self.delete_selected)

        self._menu_empty = tk.Menu(self, tearoff=False)
        self._menu_empty.add_command(label=t("outputs.refresh"), command=self.refresh)
        self._menu_empty.add_command(
            label=t("outputs.open_project_folder"),
            command=self.open_project_folder,
        )

        self._tree.bind("<Button-3>", self._on_context_menu)

    def set_project_root(self, project_root: Path | None) -> None:
        self._project_root = project_root
        self.refresh()

    def refresh(self) -> None:
        self._entries = []
        self._filtered = []
        self._row_entry_by_iid = {}

        if self._project_root is None:
            self._render_rows()
            self._preview.clear()
            return

        folders = {
            self._project_root / "outputs" / "consolidated": "Consolidated",
            self._project_root / "outputs" / "yamls": "YAML",
            self._project_root / "outputs" / "work": "Work",
            self._project_root / "logs": "Logs",
            self._project_root / "inputs" / "articles": "PDF",
        }

        for folder, default_type in folders.items():
            if not folder.exists():
                continue
            for path in sorted(folder.glob("**/*")):
                if path.is_dir():
                    continue
                ext = path.suffix.lower()
                file_type = {
                    ".yaml": "YAML",
                    ".yml": "YAML",
                    ".log": "Logs",
                    ".txt": "Logs",
                    ".csv": "CSV",
                    ".xlsx": "Consolidated",
                    ".pdf": "PDF",
                }.get(ext, default_type)
                try:
                    stat = path.stat()
                    size = stat.st_size
                    modified = stat.st_mtime
                except OSError:
                    size = 0
                    modified = 0.0
                self._entries.append(
                    OutputEntry(
                        path=path,
                        file_type=file_type,
                        size=size,
                        modified=modified,
                    )
                )

        self._apply_filter()

    def _apply_filter(self) -> None:
        type_filter = self._filter_type_var.get().strip() or "All"
        query = self._filter_text_var.get().strip().lower()

        filtered = []
        for entry in self._entries:
            if type_filter != "All" and entry.file_type != type_filter:
                continue
            if query and query not in entry.path.name.lower():
                continue
            filtered.append(entry)

        self._filtered = self._sorted_entries(filtered)
        self._render_rows()

    def _sorted_entries(self, entries: list[OutputEntry]) -> list[OutputEntry]:
        key_name = self._sort_column
        reverse = self._sort_desc

        if key_name == "type":
            key_fn = lambda item: (item.file_type.lower(), item.path.name.lower())
        elif key_name == "size":
            key_fn = lambda item: item.size
        elif key_name == "modified":
            key_fn = lambda item: item.modified
        else:
            key_fn = lambda item: item.path.name.lower()
        return sorted(entries, key=key_fn, reverse=reverse)

    def _sort_by(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_column = column
            self._sort_desc = False

        arrow = " ▼" if self._sort_desc else " ▲"
        for col in ("name", "type", "size", "modified"):
            label = {
                "name": t("outputs.col_name"),
                "type": t("outputs.col_type"),
                "size": t("outputs.col_size"),
                "modified": t("outputs.col_modified"),
            }[col]
            if col == self._sort_column:
                label += arrow
            self._tree.heading(col, text=label)

        self._filtered = self._sorted_entries(self._filtered)
        self._render_rows()

    def _render_rows(self) -> None:
        for row_id in self._tree.get_children():
            self._tree.delete(row_id)

        self._row_entry_by_iid.clear()
        for entry in self._filtered:
            rel = str(entry.path.relative_to(self._project_root)) if self._project_root else entry.path.name
            modified = self._format_modified(entry.modified)
            icon = self._icon_for_entry(entry)
            iid = self._tree.insert(
                "",
                "end",
                text="",
                image=icon,
                values=(rel, entry.file_type, self._format_size(entry.size), modified),
            )
            self._row_entry_by_iid[iid] = entry

    def _selected_entry(self) -> OutputEntry | None:
        selection = self._tree.selection()
        if not selection:
            return None
        return self._row_entry_by_iid.get(selection[0])

    def _format_modified(self, modified: float) -> str:
        if not modified:
            return "-"
        return (
            datetime.fromtimestamp(modified, tz=timezone.utc)
            .astimezone()
            .strftime("%Y-%m-%d %H:%M")
        )

    def _on_select(self, _event: object) -> None:
        entry = self._selected_entry()
        self._preview.set_file(entry.path if entry else None)

    def _open_path(self, path: Path) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            logging.getLogger("saec.gui").warning("Cannot open %s: %s", path, exc)
            messagebox.showerror("Open failed", str(exc), parent=self)

    def open_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        self._open_path(entry.path)

    def open_selected_folder(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        self._open_path(entry.path.parent)

    def open_project_folder(self) -> None:
        if self._project_root is None:
            return
        self._open_path(self._project_root)

    def copy_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        self.clipboard_clear()
        self.clipboard_append(str(entry.path))

    def delete_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        confirm = messagebox.askyesno(
            t("dialog.delete_file"),
            t("dialog.delete_confirm", filename=entry.path.name),
            parent=self,
        )
        if not confirm:
            return
        try:
            entry.path.unlink()
        except OSError as exc:
            messagebox.showerror(t("dialog.delete_failed"), str(exc), parent=self)
            return
        self.refresh()

    def _on_context_menu(self, event: tk.Event[tk.Misc]) -> None:
        row = self._tree.identify_row(event.y)
        if row:
            self._tree.selection_set(row)
            self._menu_item.tk_popup(event.x_root, event.y_root)
        else:
            self._menu_empty.tk_popup(event.x_root, event.y_root)

    def _format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def _build_icons(self) -> dict[str, tk.PhotoImage]:
        def _icon(color: str) -> tk.PhotoImage:
            img = tk.PhotoImage(width=16, height=16)
            img.put("#C0C0C0", to=(0, 0, 16, 16))
            img.put(color, to=(3, 2, 13, 14))
            img.put("#FFFFFF", to=(4, 3, 12, 4))
            return img

        return {
            "YAML": _icon("#3A6EA5"),
            "PDF": _icon("#B33A3A"),
            "Logs": _icon("#666666"),
            "CSV": _icon("#3A8B3A"),
            "Consolidated": _icon("#3A8B3A"),
            "default": _icon("#999999"),
        }

    def _icon_for_entry(self, entry: OutputEntry) -> tk.PhotoImage:
        return self._icons.get(entry.file_type, self._icons["default"])
