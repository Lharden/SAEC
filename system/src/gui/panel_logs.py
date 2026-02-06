"""Log viewer panel."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class LogsPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=4, pady=4)
        ttk.Button(toolbar, text="Clear", command=self.clear).pack(side="left")

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
        self._text.insert("end", f"{text}\n")
        self._text.see("end")

    def clear(self) -> None:
        self._text.delete("1.0", "end")
