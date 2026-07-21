# SPDX-License-Identifier: MIT
"""Cross-process file lock so two reconcile crons never tick the same ledger.

Uses exclusive create of a lock file with PID + timestamp. Stale locks older
than ``stale_seconds`` may be broken (operator policy for crashed hosts).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


class LedgerLockError(RuntimeError):
    pass


class LedgerFileLock:
    def __init__(self, lock_path: str | Path, *, stale_seconds: float = 3600.0):
        self.path = Path(lock_path)
        self.stale_seconds = float(stale_seconds)
        self._held = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "ts": time.time(),
            "host": os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "",
        }
        try:
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            self._held = True
            return
        except FileExistsError:
            pass
        # Stale?
        try:
            existing = json.loads(self.path.read_text(encoding="utf-8"))
            age = time.time() - float(existing.get("ts", 0))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            age = 0
        if age >= self.stale_seconds:
            try:
                self.path.unlink(missing_ok=True)  # type: ignore[call-arg]
            except TypeError:
                if self.path.exists():
                    self.path.unlink()
            return self.acquire()
        raise LedgerLockError(
            f"ledger lock held: {self.path} (age={age:.0f}s, "
            f"stale_after={self.stale_seconds}s)"
        )

    def release(self) -> None:
        if not self._held:
            return
        try:
            self.path.unlink(missing_ok=True)  # type: ignore[call-arg]
        except TypeError:
            if self.path.exists():
                self.path.unlink()
        self._held = False

    def __enter__(self) -> LedgerFileLock:
        self.acquire()
        return self

    def __exit__(self, *args) -> None:
        self.release()
