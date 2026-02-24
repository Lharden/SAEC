"""YAML preview panel with raw + CIMO summary modes."""

from __future__ import annotations

import logging
from pathlib import Path
import re
import tkinter as tk
from tkinter import ttk
from typing import Any

import yaml

_log = logging.getLogger("saec.gui")


class YAMLPreviewPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self._current_path: Path | None = None
        self._mode_var = tk.StringVar(value="raw")

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=4, pady=4)
        ttk.Label(toolbar, text="Preview:").pack(side="left")
        self._toggle_button = ttk.Button(
            toolbar,
            text="Switch to CIMO Summary",
            command=self._toggle_mode,
        )
        self._toggle_button.pack(side="left", padx=(6, 0))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        self._text = tk.Text(
            body,
            wrap="none",
            relief="sunken",
            borderwidth=1,
            bg="#FFFFFF",
            fg="#000000",
            insertbackground="#000000",
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

        self._text.tag_configure("key", font=("Courier New", 8, "bold"))
        self._text.tag_configure("value", foreground="#003399")
        self._text.tag_configure("header", foreground="#8B0000", font=("Courier New", 8, "bold"))

    def clear(self) -> None:
        self._current_path = None
        self._set_text("Select a YAML file to preview.")

    def set_file(self, path: Path | None) -> None:
        self._current_path = path
        self._render_current()

    def _toggle_mode(self) -> None:
        current = self._mode_var.get()
        self._mode_var.set("summary" if current == "raw" else "raw")
        if self._mode_var.get() == "summary":
            self._toggle_button.configure(text="Switch to Raw YAML")
        else:
            self._toggle_button.configure(text="Switch to CIMO Summary")
        self._render_current()

    def _render_current(self) -> None:
        path = self._current_path
        if path is None:
            self.clear()
            return
        if not path.exists():
            self._set_text(f"File not found: {path}")
            return

        if path.suffix.lower() not in (".yaml", ".yml"):
            text = path.read_text(encoding="utf-8", errors="replace")
            self._set_text(text[:60000])
            return

        raw = path.read_text(encoding="utf-8", errors="replace")
        if self._mode_var.get() == "summary":
            payload = self._load_yaml_dict(raw)
            self._set_text(self._build_summary(payload))
        else:
            self._set_text(raw)
            self._highlight_yaml()

    def _load_yaml_dict(self, raw: str) -> dict[str, Any]:
        try:
            docs = list(yaml.safe_load_all(raw))
        except Exception as exc:
            _log.warning("YAML parse failed for preview: %s", exc)
            return {}
        for payload in docs:
            if isinstance(payload, dict):
                return payload
        return {}

    def _build_summary(self, data: dict[str, Any]) -> str:
        artigo = str(data.get("ArtigoID", "-"))
        titulo = str(
            data.get("Title")
            or data.get("Titulo")
            or data.get("Título")
            or data.get("Referência_Curta")
            or "-"
        )
        context = str(data.get("ProblemaNegócio_Contexto", "-")).strip() or "-"
        intervention = str(data.get("Intervenção_Descrição", "-")).strip() or "-"
        mechanism = str(data.get("Mecanismo_Estruturado", "-")).strip() or "-"
        outcome_q = str(data.get("Resultados_Quant", "-")).strip() or "-"
        outcome_ql = str(data.get("Resultados_Qual", "-")).strip() or "-"
        quotes = data.get("Quotes", [])
        quote_count = len(quotes) if isinstance(quotes, list) else 0

        lines = [
            "CIMO Summary",
            "=" * 60,
            f"Article ID : {artigo}",
            f"Title      : {titulo}",
            "",
            "[C] Context",
            context,
            "",
            "[I] Intervention",
            intervention,
            "",
            "[M] Mechanism",
            mechanism,
            "",
            "[O] Outcomes",
            f"Quantitative: {outcome_q}",
            f"Qualitative : {outcome_ql}",
            "",
            f"Quotes: {quote_count}",
        ]
        return "\n".join(lines)

    def _set_text(self, text: str) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", text)
        self._text.see("1.0")
        self._text.configure(state="disabled")

    def _highlight_yaml(self) -> None:
        self._text.configure(state="normal")
        self._text.tag_remove("key", "1.0", "end")
        self._text.tag_remove("value", "1.0", "end")
        self._text.tag_remove("header", "1.0", "end")

        header_tokens = ("Context", "Interven", "Mecanismo", "Resultado", "Outcome")
        line_count = int(self._text.index("end-1c").split(".")[0])
        for line_no in range(1, line_count + 1):
            line_start = f"{line_no}.0"
            line_end = f"{line_no}.end"
            line = self._text.get(line_start, line_end)
            match = re.match(r"^([A-Za-z0-9_À-ÿ\- ]+):(.*)$", line)
            if not match:
                continue

            key = match.group(1)
            value = match.group(2)
            self._text.tag_add("key", line_start, f"{line_no}.{len(key)}")

            if any(token in key for token in header_tokens):
                self._text.tag_add("header", line_start, f"{line_no}.{len(key)}")

            value_clean = value.rstrip()
            if value_clean:
                value_start_col = len(key) + 1
                while value_start_col < len(line) and line[value_start_col] == " ":
                    value_start_col += 1
                self._text.tag_add(
                    "value",
                    f"{line_no}.{value_start_col}",
                    f"{line_no}.{len(line)}",
                )

        self._text.configure(state="disabled")
