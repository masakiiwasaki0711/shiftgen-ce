from __future__ import annotations

import os
from pathlib import Path
import sys
import traceback


def _show_fatal_error(title: str, body: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, body)
        root.destroy()
    except Exception:
        print(title)
        print(body)


def _find_project_venv_python() -> str | None:
    root = Path(__file__).resolve().parent
    candidates = [
        root / ".venv" / "bin" / "python",
        root / ".venv" / "Scripts" / "python.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def main() -> int:
    try:
        venv_python = _find_project_venv_python()
        if venv_python is not None:
            cur = Path(sys.executable).resolve()
            tgt = Path(venv_python).resolve()
            if cur != tgt:
                os.execv(venv_python, [venv_python, __file__, *sys.argv[1:]])

        from shiftgen.ce_gui import run_app

        run_app()
        return 0
    except Exception:
        tb = traceback.format_exc()
        _show_fatal_error("ce-shift error", tb)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
