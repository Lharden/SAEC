"""Pipeline run panel controls."""

from __future__ import annotations

import re
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from job_runner import RunRequest
from presets import list_presets, get_preset


class RunPanel(ttk.LabelFrame):
    def __init__(self, parent: tk.Misc, *, on_run, on_cancel) -> None:
        super().__init__(parent, text="Pipeline Run", style="Section.TLabelframe")
        self._on_run = on_run
        self._on_cancel = on_cancel

        self.preset_var = tk.StringVar(value="pilot")
        self.mode_var = tk.StringVar(value="step")
        self.step_var = tk.StringVar(value="2")
        self.article_var = tk.StringVar(value="")
        self.log_level_var = tk.StringVar(value="INFO")
        self.dry_run_var = tk.BooleanVar(value=False)
        self.force_var = tk.BooleanVar(value=False)
        self.preset_description_var = tk.StringVar(value="")

        self._run_button: ttk.Button | None = None
        self._cancel_button: ttk.Button | None = None
        self._validation_label: tk.Label | None = None
        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="Preset").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        preset_values = [preset.name for preset in list_presets()]
        preset_combo = ttk.Combobox(
            self,
            textvariable=self.preset_var,
            values=preset_values,
            state="readonly",
            width=18,
        )
        preset_combo.grid(row=0, column=1, sticky="w", padx=6, pady=4)
        preset_combo.bind("<<ComboboxSelected>>", self._on_preset_changed)
        ttk.Label(self, textvariable=self.preset_description_var, width=54).grid(
            row=0, column=2, columnspan=2, sticky="w", padx=6, pady=4
        )

        ttk.Label(self, text="Mode").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(
            self,
            textvariable=self.mode_var,
            values=["all", "step"],
            width=10,
            state="readonly",
        ).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(self, text="Step").grid(row=1, column=2, sticky="w", padx=6, pady=4)
        ttk.Combobox(
            self,
            textvariable=self.step_var,
            values=["1", "2", "3", "5"],
            width=6,
            state="readonly",
        ).grid(row=1, column=3, sticky="w", padx=6, pady=4)

        ttk.Label(self, text="Article ID").grid(
            row=2, column=0, sticky="w", padx=6, pady=4
        )
        ttk.Entry(self, textvariable=self.article_var, width=20).grid(
            row=2, column=1, sticky="w", padx=6, pady=4
        )

        ttk.Label(self, text="Log level").grid(
            row=2, column=2, sticky="w", padx=6, pady=4
        )
        ttk.Combobox(
            self,
            textvariable=self.log_level_var,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            width=10,
            state="readonly",
        ).grid(row=2, column=3, sticky="w", padx=6, pady=4)

        ttk.Checkbutton(self, text="Dry run", variable=self.dry_run_var).grid(
            row=3, column=0, sticky="w", padx=6, pady=4
        )
        ttk.Checkbutton(self, text="Force", variable=self.force_var).grid(
            row=3, column=1, sticky="w", padx=6, pady=4
        )

        buttons = ttk.Frame(self)
        buttons.grid(row=4, column=0, columnspan=4, sticky="w", padx=6, pady=6)

        self._run_button = ttk.Button(buttons, text="Queue Run", command=self._on_run)
        self._run_button.pack(side="left")
        self._cancel_button = ttk.Button(
            buttons, text="Cancel", command=self._on_cancel, state="disabled"
        )
        self._cancel_button.pack(side="left", padx=(6, 0))

        self._validation_label = tk.Label(
            self, text="", fg="#CC0000", bg="#C0C0C0", anchor="w", justify="left"
        )
        self._validation_label.grid(
            row=5, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 4)
        )

        self._on_preset_changed()

    def _on_preset_changed(self, _event=None) -> None:
        preset = get_preset(self.preset_var.get())
        self.mode_var.set(preset.mode)
        self.step_var.set(str(preset.step) if preset.step is not None else "2")
        self.dry_run_var.set(preset.dry_run)
        self.force_var.set(preset.force)
        self.preset_description_var.set(preset.description)

    def set_running(self, running: bool) -> None:
        if self._run_button is not None:
            self._run_button.configure(state="normal")
        if self._cancel_button is not None:
            self._cancel_button.configure(state="normal" if running else "disabled")

    def build_request(
        self, *, workspace_root: Path | None, project_root: Path | None
    ) -> RunRequest:
        mode = self.mode_var.get().strip() or "step"
        step = int(self.step_var.get()) if mode == "step" else None
        preset = get_preset(self.preset_var.get())
        return RunRequest(
            mode="all" if mode == "all" else "step",
            step=step,
            article_id=self.article_var.get().strip(),
            dry_run=bool(self.dry_run_var.get()),
            force=bool(self.force_var.get()),
            log_level=self.log_level_var.get().strip() or "INFO",
            timeout_minutes=preset.timeout_minutes,
            workspace_root=workspace_root,
            project_root=project_root,
        )

    def validate(self) -> list[str]:
        """Return list of validation error messages. Empty list means valid."""
        errors: list[str] = []

        mode = self.mode_var.get()

        # Validate step selection when in step mode
        if mode == "step":
            step = self.step_var.get()
            try:
                step_num = int(step)
                if step_num not in (1, 2, 3, 5):
                    errors.append(
                        f"Invalid step: {step_num}. Must be 1, 2, 3, or 5."
                    )
            except (ValueError, TypeError):
                errors.append("Step must be a number (1, 2, 3, or 5).")

        # Validate article ID format (if provided)
        article = self.article_var.get().strip()
        if article:
            if not re.match(r"^ART_\d{3}$", article) and not re.match(
                r"^[A-Za-z0-9_-]+$", article
            ):
                errors.append(f"Invalid article ID format: '{article}'")

        return errors

    def show_validation_errors(self, errors: list[str]) -> None:
        """Display validation errors in the panel, or clear them."""
        if self._validation_label is None:
            return
        if errors:
            self._validation_label.configure(text="\n".join(errors))
        else:
            self._validation_label.configure(text="")
