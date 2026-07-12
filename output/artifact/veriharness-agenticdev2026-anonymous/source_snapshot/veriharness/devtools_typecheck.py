from __future__ import annotations

import compileall
import importlib.util
import subprocess
import sys


def main() -> int:
    if importlib.util.find_spec("mypy") is not None:
        return subprocess.call([sys.executable, "-m", "mypy", "veriharness"])
    ok = compileall.compile_dir("veriharness", quiet=1)
    if ok:
        print("mypy is not installed; compileall fallback passed.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
