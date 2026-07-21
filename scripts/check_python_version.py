# SPDX-License-Identifier: MIT
"""Fail if the runtime is older than the engine's supported floor (3.11)."""
from __future__ import annotations

import sys


def main() -> int:
    if sys.version_info < (3, 11):
        print(
            f"ERROR: Python {sys.version.split()[0]} is too old; need 3.11+",
            file=sys.stderr,
        )
        return 1
    print(f"python_version_ok {sys.version.split()[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
