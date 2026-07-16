# SPDX-License-Identifier: MIT
"""The DRBG must be exact, uniform-enough, and immutable across versions."""
import pytest

from shipgen.drbg import Drbg, derive_seed_key, normalize_coin_id


def test_streams_are_deterministic():
    a = Drbg(b"key", "label")
    b = Drbg(b"key", "label")
    assert [a.rand_below(1000) for _ in range(100)] == \
           [b.rand_below(1000) for _ in range(100)]


def test_labels_are_independent_streams():
    assert [Drbg(b"k", "one").rand_below(10**9) for _ in range(4)] != \
           [Drbg(b"k", "two").rand_below(10**9) for _ in range(4)]


def test_known_answer_vector():
    """Golden vector: any change to the DRBG construction breaks verifiability
    of already-published commitments. If this fails, you broke the fairness
    scheme — do NOT update the expected values without a new algorithm id."""
    d = Drbg(b"sinking-ship-test-vector", "kat/v1")
    assert [d.rand_below(1_000_000) for _ in range(5)] == \
        [658375, 274555, 493271, 284473, 281771]


def test_rand_below_bounds_and_coverage():
    d = Drbg(b"k", "bounds")
    seen = {d.rand_below(7) for _ in range(500)}
    assert seen == set(range(7))
    assert d.rand_below(1) == 0
    with pytest.raises(ValueError):
        d.rand_below(0)


def test_rand_int_inclusive():
    d = Drbg(b"k", "ri")
    vals = {d.rand_int(3, 5) for _ in range(200)}
    assert vals == {3, 4, 5}


def test_weighted_index_zero_weights_never_picked():
    d = Drbg(b"k", "wi")
    picks = {d.weighted_index([0, 5, 0, 5]) for _ in range(200)}
    assert picks == {1, 3}
    with pytest.raises(ValueError):
        d.weighted_index([0, 0])


def test_weighted_index_rejects_negative_even_with_precomputed_total():
    d = Drbg(b"k", "neg")
    with pytest.raises(ValueError, match="negative"):
        d.weighted_index([1, -1, 2])
    with pytest.raises(ValueError, match="negative"):
        d.weighted_index([1, -1, 2], total=2)  # previously only checked when total is None


def test_weighted_index_precomputed_total_matches_naive():
    """Hot-path total must not change the draw sequence vs computing sum inline."""
    w = [10, 0, 30, 5]
    a = Drbg(b"k", "precomp")
    b = Drbg(b"k", "precomp")
    assert [a.weighted_index(w, total=sum(w)) for _ in range(50)] == \
           [b.weighted_index(w) for _ in range(50)]


def test_weighted_index_roughly_proportional():
    d = Drbg(b"k", "prop")
    counts = [0, 0]
    for _ in range(10_000):
        counts[d.weighted_index([900, 100])] += 1
    assert 0.85 < counts[0] / 10_000 < 0.95


def test_sample_distinct():
    d = Drbg(b"k", "sd")
    s = d.sample_distinct(44_400, 44)
    assert len(s) == len(set(s)) == 44
    assert all(0 <= v < 44_400 for v in s)
    assert d.sample_distinct(10, 0) == []
    with pytest.raises(ValueError):
        d.sample_distinct(3, 4)
    with pytest.raises(ValueError):
        d.sample_distinct(-1, 0)


def test_coin_id_normalization():
    raw = "AB" * 32
    assert normalize_coin_id("0x" + raw) == "ab" * 32
    assert normalize_coin_id(raw.lower()) == "ab" * 32
    assert derive_seed_key(b"s", "0x" + raw) == derive_seed_key(b"s", raw.lower())
    for bad in ("zz" * 32, "ab" * 31, "", "0x1234"):
        with pytest.raises(ValueError):
            normalize_coin_id(bad)
