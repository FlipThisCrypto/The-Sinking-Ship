# SPDX-License-Identifier: MIT
"""P1 grail bios: every named grail has a real, on-voice bio and the metadata
generator emits it (no placeholder text left in the mint path)."""
from __future__ import annotations

import scripts.gen_grail_stubs as mod

ALL_MEMBERS = [m for _set, members in mod.GRAIL_SETS for m in members]


def test_exactly_44_grails():
    assert len(ALL_MEMBERS) == 44
    assert len(set(ALL_MEMBERS)) == 44  # names are unique


def test_every_grail_has_a_nonempty_bio():
    missing = [m for m in ALL_MEMBERS if not mod.GRAIL_BIOS.get(m, "").strip()]
    assert not missing, f"grails missing a bio: {missing}"


def test_no_extra_or_orphaned_bios():
    extra = sorted(set(mod.GRAIL_BIOS) - set(ALL_MEMBERS))
    assert not extra, f"bios for unknown grails: {extra}"


def test_bios_are_substantive_and_placeholder_free():
    for m in ALL_MEMBERS:
        bio = mod.GRAIL_BIOS[m]
        assert len(bio) >= 60, f"bio too short for {m!r}"
        assert "placeholder" not in bio.lower(), f"placeholder text in {m!r}"


def test_generator_embeds_the_real_bio(tmp_path):
    import json

    assert mod.main.__module__  # module import side effects ran
    # Generate into a temp dir and confirm a sampled grail's bio is embedded and
    # no placeholder text survives in any description.
    rc = _run_generator(tmp_path)
    assert rc == 0
    files = sorted(tmp_path.glob("grail_*.json"))
    assert len(files) == 44
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        assert "Placeholder bio" not in doc["description"]
        member = next(a["value"] for a in doc["attributes"]
                      if a["trait_type"] == "grail_name")
        assert mod.GRAIL_BIOS[member] in doc["description"]


def _run_generator(outdir) -> int:
    import sys

    argv = sys.argv
    sys.argv = ["gen_grail_stubs.py", "--outdir", str(outdir)]
    try:
        return mod.main()
    finally:
        sys.argv = argv
