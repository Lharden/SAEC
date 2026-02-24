"""Desktop entrypoint for SAEC Win98 shell."""

from __future__ import annotations

from pathlib import Path
import sys

# Prevent .pyc bytecode caching — source changes take effect immediately
sys.dont_write_bytecode = True


PIPELINE_FLAGS = {
    "--status",
    "--step",
    "--all",
    "--article",
    "--force",
    "--dry-run",
    "--log-level",
}


def _bootstrap_paths() -> None:
    root = Path(__file__).resolve().parent
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _show_bootstrap_splash(*, duration_ms: int = 2000) -> None:
    import tkinter as tk

    from gui.splash import show_startup_splash

    splash_root = tk.Tk()
    splash_root.withdraw()
    show_startup_splash(
        splash_root,
        duration_ms=duration_ms,
        reveal_root=False,
        on_complete=splash_root.destroy,
    )
    splash_root.mainloop()


def _is_pipeline_cli_invocation(args: list[str]) -> bool:
    for arg in args:
        if arg in PIPELINE_FLAGS:
            return True
        if arg.startswith("--step="):
            return True
        if arg.startswith("--article="):
            return True
        if arg.startswith("--log-level="):
            return True
    return False


def main() -> int:
    _bootstrap_paths()

    if _is_pipeline_cli_invocation(sys.argv[1:]):
        import main as pipeline_main

        return int(pipeline_main.main())

    _show_bootstrap_splash(duration_ms=2000)

    # Load language preference before any GUI widget is created
    _load_language_from_env()

    from gui.app import SAECWin98App
    app = SAECWin98App()
    app.mainloop()
    return 0


def _load_language_from_env() -> None:
    """Read GUI_LANGUAGE from .env and set the i18n module language."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if line.startswith("GUI_LANGUAGE="):
                lang = line.split("=", 1)[1].strip().strip("\"'")
                from gui.i18n import set_language
                set_language(lang)
                return
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
