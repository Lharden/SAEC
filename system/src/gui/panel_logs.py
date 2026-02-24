"""Log viewer panel with level filtering and scrollback limit."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.tooltip import add_tooltip

_MAX_LINES = 5000
_TRIM_LINES = 1000


class LogsPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)

        self._all_lines: list[str] = []
        self._current_filter = "ALL"

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=4, pady=4)

        ttk.Label(toolbar, text="Level:").pack(side="left", padx=(0, 4))
        self._level_var = tk.StringVar(value="ALL")
        level_combo = ttk.Combobox(
            toolbar,
            textvariable=self._level_var,
            values=["ALL", "INFO", "WARNING", "ERROR"],
            state="readonly",
            width=10,
        )
        level_combo.pack(side="left", padx=(0, 8))
        level_combo.bind("<<ComboboxSelected>>", self._on_filter_changed)

        clear_button = ttk.Button(toolbar, text="Clear", command=self.clear)
        clear_button.pack(side="left")
        add_tooltip(level_combo, "Filter logs by minimum severity")
        add_tooltip(clear_button, "Clear log display and in-memory scrollback")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        self._text = tk.Text(
            body,
            wrap="none",
            height=20,
            bg="#FFFFFF",
            fg="#000000",
            insertbackground="#000000",
            relief="sunken",
            borderwidth=1,
            font=("Courier New", 8),
            state="disabled",
        )
        ybar = ttk.Scrollbar(body, orient="vertical", command=self._text.yview)
        xbar = ttk.Scrollbar(body, orient="horizontal", command=self._text.xview)
        self._text.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)

        self._text.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")

        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

    def append_line(self, text: str) -> None:
        self._all_lines.append(text)
        self._enforce_scrollback()
        if self._passes_filter(text):
            self._insert_text(f"{text}\n")

    def clear(self) -> None:
        self._all_lines.clear()
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")

    def _enforce_scrollback(self) -> None:
        if len(self._all_lines) > _MAX_LINES:
            trimmed = min(_TRIM_LINES, len(self._all_lines))
            self._all_lines = self._all_lines[trimmed:]
            self._all_lines.insert(0, f"[INFO] ... {trimmed} earlier lines trimmed ...")
            self._rebuild_display()

    def _passes_filter(self, line: str) -> bool:
        if self._current_filter == "ALL":
            return True
        level_order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
        threshold = level_order.get(self._current_filter, 2)
        for level_name, level_rank in level_order.items():
            if f"[{level_name}]" in line and level_rank <= threshold:
                return True
        # Lines without a recognized level tag pass only on ALL or INFO
        if not any(f"[{lv}]" in line for lv in level_order):
            return threshold >= 2
        return False

    def _on_filter_changed(self, _event=None) -> None:
        self._current_filter = self._level_var.get()
        self._rebuild_display()

    def _rebuild_display(self) -> None:
        filtered = [ln for ln in self._all_lines if self._passes_filter(ln)]
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        if filtered:
            self._text.insert("end", "\n".join(filtered) + "\n")
        self._text.see("end")
        self._text.configure(state="disabled")

    def _insert_text(self, text: str) -> None:
        self._text.configure(state="normal")
        self._text.insert("end", text)
        self._text.see("end")
        self._text.configure(state="disabled")
