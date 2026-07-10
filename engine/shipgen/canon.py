# SPDX-License-Identifier: MIT
"""Canonical JSON serialization and hashing.

Every hash in the provenance scheme is computed over this canonical form:
UTF-8, sorted keys, compact separators, ASCII-escaped. Any two machines
serializing the same structure produce the same bytes.
"""
from __future__ import annotations

import hashlib
import json


def canon_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canon_bytes(obj) -> bytes:
    return canon_json(obj).encode("ascii")


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def hash_obj(obj) -> str:
    """SHA-256 hex digest of an object's canonical JSON form."""
    return sha256_hex(canon_bytes(obj))


def config_bundle_hash(*docs) -> str:
    """Order-sensitive hash over a sequence of (label, document) pairs.

    Used as the config_version_hash embedded in every manifest: change any
    config byte and every downstream hash changes.
    """
    bundle = [[label, doc] for label, doc in docs]
    return hash_obj(bundle)
