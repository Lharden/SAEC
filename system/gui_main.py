"""Desktop entrypoint for SAEC Win98 shell."""

from __future__ import annotations

from pathlib import Path
import sys


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

    from gui.app import SAECWin98App

    app = SAECWin98App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
