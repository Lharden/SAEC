"""In-app help and troubleshooting dialog."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


_QUICK_START_TEXT = """Quick Start

1. Select Workspace (Browse...) and then select/create a Project.
2. Use "Browse..." next to Articles to point to a folder with PDFs,
   or copy PDF files to: projects/<project>/inputs/articles/
3. Press F5 (Refresh).
4. Run Step 1 once for new projects (creates/syncs mapping.csv).
5. Run Step 2 (ingest) and then Step 3 (extract).
6. Export summary from Pipeline > Export Summary Report.

Presets:
- pilot: single article ingest to validate your setup
- batch: full pipeline run using .env provider defaults
- local_only: forces Ollama for all extraction/repair (requires Ollama)
- api_only: disables Ollama, uses cloud API providers only
"""


_TROUBLESHOOT_TEXT = """Common Issues and Fixes

- "No PDF files found in inputs/articles/"
  Fix: copy at least one .pdf into inputs/articles and refresh.

- "Mapping file is empty" or "Mapping is out of date"
  Fix: run Step 1 (Setup) for the selected project.

- "Step 3 requires ingest outputs (hybrid.json)"
  Fix: run Step 2 first.

- "local_only preset requires Ollama connectivity"
  Fix: start Ollama (ollama serve) or choose a cloud-capable preset.

- Export says "No outputs"
  Fix: generate YAML files first (Step 3), then export.
"""


_BEST_PRACTICES_TEXT = """Best Practices

- Use one project per experiment/demo to avoid mixed history.
- Keep project path short and avoid network folders when possible.
- Review Diagnostics before large batch runs.
- If a run fails, open Queue and select the failed job to see
  classified error guidance.
- Use Dry Run when validating setup.
"""


def _add_section(notebook: ttk.Notebook, title: str, content: str) -> None:
    frame = ttk.Frame(notebook)
    notebook.add(frame, text=title)

    text = tk.Text(
        frame,
        wrap="word",
        bg="#FFFFFF",
        fg="#000000",
        font=("MS Sans Serif", 9),
        padx=8,
        pady=8,
        relief="sunken",
        borderwidth=1,
    )
    ybar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=ybar.set)
    text.insert("1.0", content)
    text.configure(state="disabled")

    text.pack(side="left", fill="both", expand=True, padx=(0, 2))
    ybar.pack(side="right", fill="y")


def show_help_dialog(parent: tk.Misc) -> None:
    dialog = tk.Toplevel(parent)
    dialog.title("SAEC Help")
    dialog.configure(bg="#C0C0C0")
    dialog.resizable(True, True)
    dialog.minsize(760, 480)

    if isinstance(parent, (tk.Tk, tk.Toplevel)):
        dialog.transient(parent)
    dialog.grab_set()

    body = tk.Frame(dialog, bg="#C0C0C0", padx=10, pady=10)
    body.pack(fill="both", expand=True)

    notebook = ttk.Notebook(body)
    notebook.pack(fill="both", expand=True)

    _add_section(notebook, "Quick Start", _QUICK_START_TEXT)
    _add_section(notebook, "Troubleshooting", _TROUBLESHOOT_TEXT)
    _add_section(notebook, "Best Practices", _BEST_PRACTICES_TEXT)

    button_row = tk.Frame(dialog, bg="#C0C0C0", padx=10, pady=8)
    button_row.pack(fill="x")

    tk.Button(
        button_row,
        text="Close",
        width=10,
        command=dialog.destroy,
        bg="#C0C0C0",
    ).pack(side="right")

    dialog.update_idletasks()
    dw = dialog.winfo_width()
    dh = dialog.winfo_height()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    x = px + (pw - dw) // 2
    y = py + (ph - dh) // 2
    dialog.geometry(f"+{x}+{y}")

    dialog.wait_window()

