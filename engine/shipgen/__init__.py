# SPDX-License-Identifier: MIT
"""shipgen — shared deterministic generation core for THE SINKING SHIP.

Pure stdlib. No network. No global state. Every random draw flows through
an explicit HMAC-SHA256 DRBG so identical inputs produce byte-identical
results on any machine (ADR-0002).
"""

__version__ = "1.0.0"

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]
RARITY_RANK = {name: i for i, name in enumerate(RARITY_ORDER)}
