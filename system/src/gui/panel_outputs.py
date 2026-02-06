"""Output explorer panel."""

from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk


class OutputsPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self._project_root: Path | None = None
        self._items: list[Path] = []

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=4, pady=4)
        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(toolbar, text="Open", command=self.open_selected).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(toolbar, text="Copy Path", command=self.copy_selected).pack(
            side="left", padx=(4, 0)
        )

        self._list = tk.Listbox(
            self, height=16, relief="sunken", borderwidth=1, font=("MS Sans Serif", 8)
        )
        self._list.pack(fill="both", expand=True, padx=4, pady=(0, 4))

    def set_project_root(self, project_root: Path | None) -> None:
        self._project_root = project_root
        self.refresh()

    def refresh(self) -> None:
        self._list.delete(0, "end")
        self._items = []
        if self._project_root is None:
            return

        targets = [
            self._project_root / "outputs" / "consolidated",
            self._project_root / "outputs" / "yamls",
            self._project_root / "outputs" / "work",
            self._project_root / "logs",
        ]
        for folder in targets:
            if not folder.exists():
                continue
            for item in sorted(folder.glob("**/*")):
                if item.is_dir():
                    continue
                self._items.append(item)
                rel = item.relative_to(self._project_root)
                self._list.insert("end", str(rel))

    def _selected_path(self) -> Path | None:
        selection = self._list.curselection()
        if not selection:
            return None
        index = int(selection[0])
        if index >= len(self._items):
            return None
        return self._items[index]

    def open_selected(self) -> None:
        path = self._selected_path()
        if path is None:
            return
        if os.name == "nt":
            os.startfile(str(path))

    def copy_selected(self) -> None:
        path = self._selected_path()
        if path is None:
            return
        self.clipboard_clear()
        self.clipboard_append(str(path))
