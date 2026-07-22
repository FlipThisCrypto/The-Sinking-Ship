# SPDX-License-Identifier: MIT
"""On-chain collection identity validation (OPS-1).

The project DID, royalty address, and collection id in config/collection.json
are what marketplaces and the mint bind to. A placeholder or malformed value
that slips through would mint 44,444 NFTs under the wrong (or a nonsense)
identity — unrecoverable after commitment. This module is the single source of
truth for "is the chain identity real and well-formed?", used by both
validate_configs (CI gate) and ops_preflight (go/no-go gate).
"""
from __future__ import annotations

import re

# Chia DIDs and addresses are bech32m: hrp + "1" + data (charset excludes
# 1/b/i/o). We validate shape and charset, not the checksum — a typo that
# still checksums is out of scope, but structural/placeholder errors are the
# real risk here and these catch them.
_BECH32M = "[qpzry9x8gf2tvdw0s3jn54khce6mua7l]"
DID_RE = re.compile(rf"^did:chia:1{_BECH32M}{{50,}}$")
XCH_ADDR_RE = re.compile(rf"^xch1{_BECH32M}{{50,}}$")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_PLACEHOLDER = re.compile(r"todo|placeholder|xxx|change[-_ ]?me|example", re.IGNORECASE)


def check_chain_identity(collection_doc: dict) -> list[str]:
    """Return a list of problems (empty == valid) for a collection.json doc.

    Enforces: collection.id is a UUID (OQ-8 resolved to the CHIP-0007 UUID
    form); minting.did is a well-formed did:chia address; minting.royalty_address
    is a well-formed xch1 address; nothing is a leftover placeholder.
    """
    problems: list[str] = []
    coll = collection_doc.get("collection", {})
    mint = collection_doc.get("minting", {})

    cid = str(coll.get("id", ""))
    if not UUID_RE.match(cid):
        problems.append(f"collection.id must be a UUID (OQ-8), got {cid!r}")

    did = str(mint.get("did", ""))
    if not DID_RE.match(did):
        problems.append(f"minting.did must be a did:chia bech32m address, got {did!r}")

    addr = str(mint.get("royalty_address", ""))
    if not XCH_ADDR_RE.match(addr):
        problems.append(
            f"minting.royalty_address must be an xch1 bech32m address, got {addr!r}")

    bps = mint.get("royalty_percentage_basis_points")
    if not isinstance(bps, int) or isinstance(bps, bool) or not (0 <= bps <= 10000):
        problems.append(f"royalty_percentage_basis_points must be int 0..10000, got {bps!r}")

    for label, value in (("collection.id", cid), ("minting.did", did),
                         ("minting.royalty_address", addr)):
        if _PLACEHOLDER.search(value):
            problems.append(f"{label} still contains placeholder text: {value!r}")

    return problems
