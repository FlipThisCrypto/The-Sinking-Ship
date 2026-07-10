# SPDX-License-Identifier: MIT
"""Deterministic NFT / chest rolling (ADR-0002, ADR-0003).

Everything here is pure integer math over HMAC-DRBG streams:

    seed_key  = HMAC-SHA256(secret_salt, payment_coin_id)      (spec 5.4)
    each draw = named substream of seed_key

Layers roll in traits.json `roll_order` (chosen so all bias rules point
forward). Hard cross-layer rules that cannot be expressed forward are
enforced by whole-NFT rejection on a deterministic nonce ladder. Global
quotas (The Torn) and grail placements are pre-committed index sets derived
from the salt — see derive_placements().
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from . import RARITY_ORDER, RARITY_RANK
from .config import GenConfig
from .drbg import Drbg, derive_seed_key

MAX_NFT_ATTEMPTS = 64
MAX_PITY_ATTEMPTS = 64
LUCK_BASE = 1000  # permille

# ranks: -1 none/quota, 0..5 common..mythic
EPIC_RANK = RARITY_RANK["epic"]
MYTHIC_RANK = RARITY_RANK["mythic"]


@dataclass
class RolledNft:
    traits: dict          # layer name -> trait name (roll_order order)
    rarity_tier: str
    nonce: int
    the_torn: bool = False
    pity_upgraded: bool = False


class RollEngine:
    """Precompiled, immutable view of the config for fast deterministic rolls."""

    def __init__(self, cfg: GenConfig):
        if cfg.weights is None:
            raise ValueError("RollEngine requires weights.json")
        self.cfg = cfg
        self.roll_order = list(cfg.roll_order)
        self._layer = {}
        for layer in cfg.layers:
            names = [t.name for t in layer.traits]
            ranks = [t.rarity_rank for t in layer.traits]
            weights = [int(cfg.weights[layer.name][t.name]) for t in layer.traits]
            self._layer[layer.name] = (names, ranks, weights)

        # forward effects: (if_layer, if_trait) -> list of (target_layer, kind, payload)
        self._forward: dict[tuple[str, str], list] = {}
        self._post_require_any: list[dict] = []
        self._combo_gates: list[dict] = []

        def add_forward(key, effect):
            self._forward.setdefault(key, []).append(effect)

        for rule in cfg.exclusions:
            rtype = rule["type"]
            if rtype == "note":
                continue
            if rtype == "exclude":
                key = (rule["if"]["layer"], rule["if"]["trait"])
                add_forward(key, (rule["then"]["layer"], "exclude",
                                  frozenset(rule["then"]["traits"])))
            elif rtype == "require":
                key = (rule["if"]["layer"], rule["if"]["trait"])
                add_forward(key, (rule["then"]["layer"], "require",
                                  frozenset(rule["then"]["traits"])))
            elif rtype == "require_any":
                self._post_require_any.append(rule)
            elif rtype == "combo_gate":
                self._combo_gates.append(rule)
            else:
                raise ValueError(f"unknown exclusion type {rtype!r} in {rule['id']}")

        self._clusters: list[dict] = []
        for rule in cfg.pairings:
            rtype = rule["type"]
            if rtype == "bias":
                key = (rule["if"]["layer"], rule["if"]["trait"])
                mult = _permille(rule["then"]["weight_multiplier"])
                add_forward(key, (rule["then"]["layer"], "mult",
                                  {t: mult for t in rule["then"]["traits"]}))
            elif rtype == "bias_multi":
                key = (rule["if"]["layer"], rule["if"]["trait"])
                for part in rule["then"]:
                    mult = _permille(part["weight_multiplier"])
                    add_forward(key, (part["layer"], "mult",
                                      {t: mult for t in part["traits"]}))
            elif rtype == "cluster":
                self._clusters.append({
                    "members": [(m["layer"], m["trait"]) for m in rule["cluster_traits"]],
                    "min_present": int(rule["min_present"]),
                    "mult": _permille(rule["weight_multiplier"]),
                })
            else:
                raise ValueError(f"unknown pairing type {rtype!r} in {rule['id']}")

        self._forced_aura = None
        for rule in cfg.rules:
            if rule["type"] == "forced_aura":
                self._forced_aura = rule

        # roll_order sanity: every forward rule must point forward
        order_pos = {name: i for i, name in enumerate(self.roll_order)}
        for (if_layer, _), effects in self._forward.items():
            for target, _, _ in effects:
                if order_pos[target] <= order_pos[if_layer]:
                    raise ValueError(
                        f"rule from {if_layer} to {target} is not forward in roll_order")

    # ------------------------------------------------------------------ NFT

    def roll_nft(self, seed_key: bytes, label: str, luck_permille: int = LUCK_BASE,
                 restrict: tuple[str, int] | None = None) -> RolledNft:
        """Roll one NFT deterministically.

        restrict=(layer_name, min_rank) is the pity-upgrade mechanism: that
        one layer's candidates are limited to traits with rank >= min_rank.
        """
        for nonce in range(MAX_NFT_ATTEMPTS):
            rolled = self._attempt(seed_key, label, nonce, luck_permille, restrict)
            if rolled is not None:
                return rolled
        raise RuntimeError(
            f"roll_nft exceeded {MAX_NFT_ATTEMPTS} attempts for {label!r} — "
            "constraints are likely unsatisfiable; check config")

    def _attempt(self, seed_key, label, nonce, luck_permille, restrict):
        drbg = Drbg(seed_key, f"{label}/nft/{nonce}")
        traits: dict[str, str] = {}
        active_excl: dict[str, set] = {}
        active_req: dict[str, frozenset] = {}
        active_mult: dict[str, dict] = {}

        for layer_name in self.roll_order:
            names, ranks, base = self._layer[layer_name]
            weights = []
            req = active_req.get(layer_name)
            excl = active_excl.get(layer_name)
            mults = active_mult.get(layer_name)
            cluster_boost = self._cluster_boost(layer_name, traits)
            for i, name in enumerate(names):
                w = base[i]
                if w > 0:
                    if ranks[i] >= EPIC_RANK and luck_permille != LUCK_BASE:
                        w = w * luck_permille // LUCK_BASE
                    if req is not None and name not in req:
                        w = 0
                    elif excl is not None and name in excl:
                        w = 0
                    if w > 0 and restrict is not None and layer_name == restrict[0] \
                            and ranks[i] < restrict[1]:
                        w = 0
                    if w > 0 and mults is not None and name in mults:
                        w = w * mults[name] // 1000
                    if w > 0 and cluster_boost is not None and name in cluster_boost:
                        w = w * cluster_boost[name] // 1000
                weights.append(w)
            if not any(weights):
                return None  # over-constrained this attempt; try next nonce
            idx = drbg.weighted_index(weights)
            chosen = names[idx]
            traits[layer_name] = chosen

            for target, kind, payload in self._forward.get((layer_name, chosen), []):
                if kind == "exclude":
                    active_excl.setdefault(target, set()).update(payload)
                elif kind == "require":
                    # intersect if multiple requires stack
                    prev = active_req.get(target)
                    active_req[target] = payload if prev is None else prev & payload
                elif kind == "mult":
                    slot = active_mult.setdefault(target, {})
                    for t, m in payload.items():
                        slot[t] = slot.get(t, 1000) * m // 1000

        # post-roll hard checks
        for rule in self._post_require_any:
            cond = rule["if"]
            if traits.get(cond["layer"]) == cond["trait"]:
                ok = any(traits.get(alt["layer"]) in alt["traits"]
                         for alt in rule["then"]["any_of"])
                if not ok:
                    return None

        tier = self.rarity_tier(traits)

        for gate in self._combo_gates:
            if all(traits.get(m["layer"]) == m["trait"] for m in gate["combo"]):
                need = RARITY_RANK[gate["allowed_only_if_tier_at_least"]]
                if RARITY_RANK.get(tier, -1) < need:
                    return None

        # Mythic rolls force an aura (spec 4.1)
        if self._forced_aura and tier == "mythic":
            aura_layer = self._forced_aura["then"]["layer"]
            banned = set(self._forced_aura["then"]["exclude_traits"])
            if traits.get(aura_layer) in banned:
                fixed = self._reroll_layer(
                    seed_key, f"{label}/forced-aura/{nonce}", aura_layer,
                    traits, active_req, active_excl, active_mult,
                    luck_permille, banned)
                if fixed is None:
                    return None
                traits[aura_layer] = fixed
                tier = self.rarity_tier(traits)

        return RolledNft(traits=traits, rarity_tier=tier, nonce=nonce)

    def _reroll_layer(self, seed_key, label, layer_name, traits,
                      active_req, active_excl, active_mult, luck_permille, banned):
        names, ranks, base = self._layer[layer_name]
        drbg = Drbg(seed_key, label)
        req = active_req.get(layer_name)
        excl = active_excl.get(layer_name)
        mults = active_mult.get(layer_name)
        cluster_boost = self._cluster_boost(layer_name, traits)
        weights = []
        for i, name in enumerate(names):
            w = base[i]
            if w > 0 and name in banned:
                w = 0
            if w > 0:
                if ranks[i] >= EPIC_RANK and luck_permille != LUCK_BASE:
                    w = w * luck_permille // LUCK_BASE
                if req is not None and name not in req:
                    w = 0
                elif excl is not None and name in excl:
                    w = 0
                if w > 0 and mults is not None and name in mults:
                    w = w * mults[name] // 1000
                if w > 0 and cluster_boost is not None and name in cluster_boost:
                    w = w * cluster_boost[name] // 1000
            weights.append(w)
        if not any(weights):
            return None
        return names[drbg.weighted_index(weights)]

    def _cluster_boost(self, layer_name, traits):
        boost = None
        for cl in self._clusters:
            present = sum(1 for (lay, tr) in cl["members"] if traits.get(lay) == tr)
            if present >= cl["min_present"]:
                for (lay, tr) in cl["members"]:
                    if lay == layer_name and lay not in traits:
                        if boost is None:
                            boost = {}
                        boost[tr] = boost.get(tr, 1000) * cl["mult"] // 1000
        return boost

    def rarity_tier(self, traits: dict[str, str]) -> str:
        best = 0
        for layer_name, trait_name in traits.items():
            names, ranks, _ = self._layer[layer_name]
            r = ranks[names.index(trait_name)] if trait_name in names else -1
            if r > best:
                best = r
        return RARITY_ORDER[best]

    # ---------------------------------------------------------------- chest

    def roll_chest(self, salt: bytes, coin_id: str, tier_name: str,
                   pass_ordinal: int, start_index: int,
                   placements: dict, provenance_hash: str) -> dict:
        """Roll a full chest manifest. Deterministic in all arguments."""
        cfg = self.cfg
        tier = cfg.tiers.get(tier_name)
        if tier is None:
            raise ValueError(f"unknown tier {tier_name!r}; valid: {sorted(cfg.tiers)}")
        if not (1 <= pass_ordinal <= tier["passes"]):
            raise ValueError(f"pass_ordinal must be in [1, {tier['passes']}] for {tier_name}")
        luck = int(tier["depth_luck_permille"])

        seed_key = derive_seed_key(salt, coin_id)
        qty = Drbg(seed_key, "chest/quantity").rand_int(tier["chest_min"], tier["chest_max"])

        grail_numbers = _grails_for_pass(placements, tier_name, pass_ordinal)
        extra_grail = bool(tier["guarantee"] and tier["guarantee"].get("guaranteed_grail"))
        n_inline = 0 if extra_grail else len(grail_numbers)
        grail_slots: dict[int, int] = {}
        if n_inline:
            picks = Drbg(seed_key, "chest/grail-slots").sample_distinct(qty, n_inline)
            for g, slot0 in zip(grail_numbers, picks):
                grail_slots[slot0 + 1] = g

        torn_slots: frozenset = frozenset(placements["torn_slots"])

        entries = []
        gen_count = 0
        torn_hits = []
        for slot in range(1, qty + 1):
            if slot in grail_slots:
                entries.append({
                    "slot": slot, "type": "grail",
                    "grail_number": grail_slots[slot],
                })
                continue
            global_index = start_index + gen_count
            gen_count += 1
            nft = self.roll_nft(seed_key, f"slot/{slot}", luck)
            if global_index in torn_slots:
                nft = self._apply_torn(nft)
                torn_hits.append(global_index)
            entries.append(_nft_entry(slot, global_index, nft))

        if extra_grail and grail_numbers:
            entries.append({
                "slot": qty + 1, "type": "grail",
                "grail_number": grail_numbers[0],
            })

        # pity guarantees (spec 5.2): deterministic upgrade of rolled NFTs
        pity_slots = self._enforce_guarantee(
            seed_key, tier, entries, luck)

        manifest = {
            "schema": "chest-manifest-v1",
            "engine": "shipgen-1.0.0",
            "config_version_hash": cfg.config_hash,
            "provenance_commitment": provenance_hash,
            "tier": tier_name,
            "zone": tier["zone"],
            "coin_id": _norm_coin(coin_id),
            "pass_ordinal": pass_ordinal,
            "start_index": start_index,
            "quantity": len(entries),
            "generated_count": gen_count,
            "depth_luck_permille": luck,
            "guarantee": tier["guarantee"],
            "pity_upgraded_slots": pity_slots,
            "the_torn_indices": torn_hits,
            "nfts": entries,
        }
        from .canon import hash_obj
        manifest["manifest_hash"] = hash_obj(manifest)
        return manifest

    def _apply_torn(self, nft: RolledNft) -> RolledNft:
        quota = self.cfg.quotas[0]
        layer, trait = quota["assign"]["layer"], quota["assign"]["trait"]
        nft.traits[layer] = trait
        nft.the_torn = True
        nft.rarity_tier = self.rarity_tier(nft.traits)
        return nft

    def _enforce_guarantee(self, seed_key, tier, entries, luck) -> list[int]:
        g = tier["guarantee"]
        if not g or "min_tier" not in g:
            return []
        need_rank = RARITY_RANK[g["min_tier"]]
        need_count = int(g["count"])

        def qualifies(e):
            if e["type"] == "grail":
                return True  # a grail outranks every floor
            if e.get("the_torn"):
                # The Torn is a committed quota placement and sub-grail meme tier
                # (spec 3). It is immutable: counting it as qualifying keeps pity
                # from ever selecting and re-rolling it, which would otherwise
                # strip its Halo+Horns and contradict manifest.the_torn_indices.
                return True
            return RARITY_RANK[e["rarity_tier"]] >= need_rank

        have = sum(1 for e in entries if qualifies(e))
        if have >= need_count:
            return []

        pity = Drbg(seed_key, "chest/pity")
        eligible_layers = self._layers_with_rank(need_rank)
        upgraded = []
        for _ in range(need_count - have):
            candidates = [i for i, e in enumerate(entries) if not qualifies(e)]
            if not candidates:
                break
            pick = candidates[pity.rand_below(len(candidates))]
            entry = entries[pick]
            carrier = eligible_layers[pity.rand_below(len(eligible_layers))]
            nft = self.roll_nft(seed_key, f"pity/{entry['slot']}", luck,
                                restrict=(carrier, need_rank))
            nft.pity_upgraded = True
            new_entry = _nft_entry(entry["slot"], entry["global_index"], nft)
            entries[pick] = new_entry
            upgraded.append(entry["slot"])
        return sorted(upgraded)

    def _layers_with_rank(self, min_rank: int) -> list[str]:
        out = []
        for layer_name in self.roll_order:
            names, ranks, base = self._layer[layer_name]
            if any(r >= min_rank and w > 0 for r, w in zip(ranks, base)):
                out.append(layer_name)
        return out


# ------------------------------------------------------------------ commit


def derive_placements(salt: bytes, cfg: GenConfig) -> dict:
    """All globally-coordinated randomness, fixed at commit time (ADR-0003).

    Derived purely from the salt, so `verify` can recompute it after reveal.
    """
    root = hmac.new(salt, b"sinking-ship-commitment-root", hashlib.sha256).digest()

    torn_quota = next(q for q in cfg.quotas if q["name"] == "the_torn")
    pool = int(cfg.supply["generated_pool"])
    torn = Drbg(root, "the-torn-slots-v1").sample_distinct(pool, int(torn_quota["count"]))
    torn_slots = sorted(i + 1 for i in torn)  # global mint indices are 1-based

    gs = cfg.grail_seeding
    grail_count = int(cfg.supply["grail_count"])
    gd = Drbg(root, "grail-placement-v1")
    order = list(range(1, grail_count + 1))
    _shuffle(gd, order)
    n_adm, n_mid, n_wiz = gs["admiral_chests"], gs["mid_tier_chests"], gs["wizard_of_the_deep"]
    admiral_grails = order[:n_adm]
    mid_grails = order[n_adm:n_adm + n_mid]
    wizard_grail = order[n_adm + n_mid:n_adm + n_mid + n_wiz]
    auction_grails = sorted(order[n_adm + n_mid + n_wiz:])
    assert len(auction_grails) == gs["auction"]

    admiral_tier = next(t for t in cfg.tiers_doc["tiers"] if t["zone"] == "hadal"
                        and t["guarantee"] and t["guarantee"].get("grail_lottery"))
    admiral: dict[str, list[int]] = {}
    for g in admiral_grails:
        p = gd.rand_int(1, admiral_tier["passes"])
        admiral.setdefault(str(p), []).append(g)

    lo, hi = gs["mid_tier_range"]
    mid_passes = []
    for t in cfg.tiers_doc["tiers"]:
        if lo <= t["id"] <= hi:
            for p in range(1, t["passes"] + 1):
                mid_passes.append((t["name"], p))
    picks = gd.sample_distinct(len(mid_passes), len(mid_grails))
    mid = [{"tier": mid_passes[i][0], "pass_ordinal": mid_passes[i][1], "grail_number": g}
           for g, i in zip(mid_grails, picks)]
    mid.sort(key=lambda m: (m["tier"], m["pass_ordinal"]))

    wizard_tier = next(t for t in cfg.tiers_doc["tiers"]
                       if t["guarantee"] and t["guarantee"].get("guaranteed_grail"))

    return {
        "torn_slots": torn_slots,
        "grails": {
            "admiral": {"tier": admiral_tier["name"], "by_pass": admiral},
            "mid": mid,
            "wizard": {"tier": wizard_tier["name"], "grail_number": wizard_grail},
            "auction": auction_grails,
        },
    }


def build_commitment(salt: bytes, cfg: GenConfig) -> dict:
    """The private commitment document. Publish only its hash pre-mint."""
    from .canon import hash_obj
    from .drbg import ALGORITHM_ID
    placements = derive_placements(salt, cfg)
    doc = {
        "scheme": "sinking-ship-commit-v1",
        "rng_algorithm": ALGORITHM_ID,
        "engine": "shipgen-1.0.0",
        "config_hash": cfg.config_hash,
        "placements": placements,
        "salt_hex": salt.hex(),
    }
    return {"commitment": doc, "commitment_hash": hash_obj(doc)}


# ------------------------------------------------------------------ helpers


def _nft_entry(slot: int, global_index: int, nft: RolledNft) -> dict:
    return {
        "slot": slot,
        "type": "generated",
        "global_index": global_index,
        "traits": nft.traits,
        "rarity_tier": nft.rarity_tier,
        "the_torn": nft.the_torn,
        "pity_upgraded": nft.pity_upgraded,
        "roll_nonce": nft.nonce,
    }


def _grails_for_pass(placements: dict, tier_name: str, pass_ordinal: int) -> list[int]:
    grails = placements["grails"]
    out: list[int] = []
    adm = grails["admiral"]
    if adm["tier"] == tier_name:
        out.extend(adm["by_pass"].get(str(pass_ordinal), []))
    for m in grails["mid"]:
        if m["tier"] == tier_name and m["pass_ordinal"] == pass_ordinal:
            out.append(m["grail_number"])
    wiz = grails["wizard"]
    if wiz["tier"] == tier_name:
        out.extend(wiz["grail_number"])
    return out


def _permille(x) -> int:
    return int(round(float(x) * 1000))


def _norm_coin(coin_id: str) -> str:
    from .drbg import normalize_coin_id
    return normalize_coin_id(coin_id)


def _shuffle(drbg: Drbg, items: list) -> None:
    """Fisher–Yates with DRBG draws (in place, deterministic)."""
    for i in range(len(items) - 1, 0, -1):
        j = drbg.rand_below(i + 1)
        items[i], items[j] = items[j], items[i]
