# SPDX-License-Identifier: MIT
from __future__ import annotations

import pytest

from fulfillment.reconcile_lock import LedgerFileLock, LedgerLockError


def test_exclusive_lock(tmp_path):
    path = tmp_path / "l.lock"
    a = LedgerFileLock(path, stale_seconds=3600)
    a.acquire()
    b = LedgerFileLock(path, stale_seconds=3600)
    with pytest.raises(LedgerLockError):
        b.acquire()
    a.release()
    b.acquire()
    b.release()


def test_stale_lock_break(tmp_path):
    path = tmp_path / "l.lock"
    path.write_text('{"pid": 1, "ts": 0}', encoding="utf-8")
    lock = LedgerFileLock(path, stale_seconds=1)
    lock.acquire()  # should break stale
    lock.release()
