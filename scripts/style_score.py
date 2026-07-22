# SPDX-License-Identifier: MIT
"""Score images against the ships_amano / art-reference visual grammar.

Metrics (each 0–100, equal weight → overall %):
  white_ground   — fraction of near-white pixels among opaque samples
  edge_density   — ink-line density (refs ~0.11–0.20)
  vertical_ramp  — warm-top → cool-bottom correlation on edge pixels
  low_flat_fill  — penalize large dark solid blocks (anti-placeholder)
  sparseness     — prefer white-dominant compositions (tattoo-clean)

Usage:
    python scripts/style_score.py
    python scripts/style_score.py --samples output/style_loop --threshold 92
    python scripts/style_score.py --self-check   # score the golden refs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
# Primary golden set = ships_amano (capital-ship style floor).
# Optional character/pirate dirs still usable via --refs.
DEFAULT_REFS = [ROOT / "ships_amano"]
EXTENDED_REFS = [
    ROOT / "ships_amano",
    ROOT / "docs" / "art-reference" / "pirate-ship",
    ROOT / "docs" / "art-reference" / "tom-bepe-amano",
]

# Empirical targets from ships_amano analysis (2026-07-10)
TARGETS = {
    "white_ground": 0.72,   # ships_amano mean ~0.75
    "edge_density": 0.19,   # ships_amano ~0.15–0.23
    "vertical_ramp": 0.55,  # |corr| of Y with (blue−red); direction may flip
    "dark_fill": 0.14,      # lower is better when too high
    "mean_luma_opaque": 0.78,
}


def _load(path: Path) -> np.ndarray:
    im = Image.open(path).convert("RGBA")
    # score at fixed resolution for stability
    if max(im.size) > 768:
        im = im.resize((768, 768), Image.LANCZOS)
    return np.asarray(im, dtype=np.float32)


def measure(path: Path) -> dict[str, float]:
    a = _load(path)
    rgb, al = a[:, :, :3], a[:, :, 3]
    opaque = al > 200
    n = int(opaque.sum()) or 1
    luma = rgb.mean(axis=2)
    white = float(((luma > 235) & opaque).sum() / n)
    dark = float(((luma < 70) & opaque).sum() / n)
    mean_luma = float(luma[opaque].mean() / 255.0) if opaque.any() else 0.0

    gy = np.abs(np.diff(luma, axis=0, prepend=luma[:1]))
    gx = np.abs(np.diff(luma, axis=1, prepend=luma[:, :1]))
    edges = ((gx + gy) > 22) & opaque
    edge_frac = float(edges.sum() / n)

    ys, xs = np.where(edges)
    if len(ys) > 30:
        ynorm = ys / max(1, a.shape[0] - 1)
        r = rgb[:, :, 0][edges]
        g = rgb[:, :, 1][edges]
        b = rgb[:, :, 2][edges]
        # Vertical colour story: strongest |corr| among warm/cool channel
        # pairs (covers crimson→navy, green→navy, gold→navy).
        corrs = []
        for series in (b - r, b - g, r - b):
            c = float(np.corrcoef(ynorm, series)[0, 1])
            if not np.isnan(c):
                corrs.append(abs(c))
        corr = max(corrs) if corrs else 0.0
    else:
        corr = 0.0

    return {
        "white_ground": white,
        "edge_density": edge_frac,
        "vertical_ramp": corr,
        "dark_fill": dark,
        "mean_luma_opaque": mean_luma,
        "path": str(path),
    }


def _band_score(value: float, target: float, lo_frac: float = 0.35, hi_frac: float = 0.55) -> float:
    """100 at target; linear falloff outside [target*(1-lo), target*(1+hi)]."""
    lo = target * (1 - lo_frac)
    hi = target * (1 + hi_frac)
    if lo <= value <= hi:
        # inside band: peak at target
        if value <= target:
            return 70 + 30 * (value - lo) / max(1e-6, target - lo)
        return 70 + 30 * (hi - value) / max(1e-6, hi - target)
    if value < lo:
        return max(0.0, 70 * value / max(1e-6, lo))
    # too high
    over = (value - hi) / max(1e-6, target)
    return max(0.0, 70 * math_exp_decay(over))


def math_exp_decay(over: float) -> float:
    return float(np.exp(-over * 1.8))


def _high_good(value: float, target: float) -> float:
    """Score where higher is better up to target, then plateau."""
    if value >= target:
        # mild penalty for overshoot past 1.15*target
        if value > target * 1.25:
            return max(50.0, 100 - (value - target * 1.25) * 80)
        return 100.0
    return max(0.0, 100.0 * (value / max(1e-6, target)))


def _low_good(value: float, target: float) -> float:
    """Score where at-or-below target is 100; excess is penalized."""
    if value <= target:
        return 100.0
    over = (value - target) / max(1e-6, target)
    return max(0.0, 100.0 * np.exp(-over * 1.4))


def score_metrics(m: dict[str, float]) -> dict[str, float]:
    parts = {
        "white_ground": _high_good(m["white_ground"], TARGETS["white_ground"]),
        "edge_density": _band_score(m["edge_density"], TARGETS["edge_density"], 0.4, 0.7),
        "vertical_ramp": _high_good(m["vertical_ramp"], TARGETS["vertical_ramp"]),
        "low_flat_fill": _low_good(m["dark_fill"], TARGETS["dark_fill"]),
        "sparseness": _high_good(m["mean_luma_opaque"], TARGETS["mean_luma_opaque"]),
    }
    overall = float(np.mean(list(parts.values())))
    parts["overall"] = overall
    return parts


def gather_images(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            out.append(p)
        elif p.is_dir():
            for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                out.extend(sorted(p.glob(ext)))
    return out


def score_paths(paths: list[Path]) -> list[dict]:
    rows = []
    for p in paths:
        m = measure(p)
        s = score_metrics(m)
        rows.append({"file": p.name, "metrics": m, "scores": s})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refs", nargs="*", type=Path, default=None,
                    help="golden reference dirs/files (default: ships_amano/)")
    ap.add_argument("--extended-refs", action="store_true",
                    help="also include pirate-ship/ and tom-bepe-amano/")
    ap.add_argument("--samples", nargs="*", type=Path, default=None,
                    help="images/dirs to score (default: output/style_loop then output/v2art)")
    ap.add_argument("--threshold", type=float, default=92.0,
                    help="pass bar for overall score (default 92)")
    ap.add_argument("--self-check", action="store_true",
                    help="only score golden refs (sanity: should score high)")
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.refs:
        ref_dirs = args.refs
    elif args.extended_refs:
        ref_dirs = EXTENDED_REFS
    else:
        ref_dirs = DEFAULT_REFS
    refs = gather_images(ref_dirs)
    if not refs:
        print("ERROR: no reference images found", file=sys.stderr)
        return 2

    ref_rows = score_paths(refs)
    ref_mean = float(np.mean([r["scores"]["overall"] for r in ref_rows]))

    if args.self_check:
        samples_paths: list[Path] = []
        sample_rows = []
    else:
        if args.samples:
            samples_paths = gather_images(args.samples)
        else:
            candidates = [
                ROOT / "output" / "style_loop",
                ROOT / "output" / "v2art",
                ROOT / "output" / "illus",
            ]
            samples_paths = []
            for c in candidates:
                samples_paths = gather_images([c])
                if samples_paths:
                    break
        sample_rows = score_paths(samples_paths) if samples_paths else []

    if not args.quiet:
        print(f"Golden refs: {len(ref_rows)} images, mean overall {ref_mean:.1f}%")
        print(f"  target axes: white>={TARGETS['white_ground']}, "
              f"edge~={TARGETS['edge_density']}, ramp>={TARGETS['vertical_ramp']}, "
              f"dark<={TARGETS['dark_fill']}")

        if sample_rows:
            mean = float(np.mean([r["scores"]["overall"] for r in sample_rows]))
            print(f"\nSamples: {len(sample_rows)} images, mean overall {mean:.1f}% "
                  f"(threshold {args.threshold:.0f}%)")
            print(f"{'file':40s} {'all':>6} {'white':>6} {'edge':>6} {'ramp':>6} "
                  f"{'fill':>6} {'sparse':>6}")
            for r in sorted(sample_rows, key=lambda x: -x["scores"]["overall"]):
                s = r["scores"]
                print(f"{r['file'][:40]:40s} {s['overall']:6.1f} {s['white_ground']:6.1f} "
                      f"{s['edge_density']:6.1f} {s['vertical_ramp']:6.1f} "
                      f"{s['low_flat_fill']:6.1f} {s['sparseness']:6.1f}")
        elif not args.self_check:
            print("\nNo sample images found. Generate with:")
            print("  python scripts/gen_placeholder_sprites.py --force --profile illustration")
            print("  python engine/render_engine.py --sample 6 --seed style --outdir output/style_loop --sizes 512")

    report = {
        "targets": TARGETS,
        "threshold": args.threshold,
        "refs_mean_overall": ref_mean,
        "refs": [{"file": r["file"], "overall": r["scores"]["overall"]} for r in ref_rows],
        "samples": [
            {"file": r["file"], "overall": r["scores"]["overall"], "scores": r["scores"],
             "metrics": {k: v for k, v in r["metrics"].items() if k != "path"}}
            for r in sample_rows
        ],
    }
    if sample_rows:
        report["samples_mean_overall"] = float(
            np.mean([r["scores"]["overall"] for r in sample_rows])
        )
        report["pass"] = report["samples_mean_overall"] >= args.threshold
    else:
        report["samples_mean_overall"] = None
        report["pass"] = None

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json_out}")

    if args.self_check:
        # refs should average well above 85 on their own grammar
        ok = ref_mean >= 80.0
        if not args.quiet:
            print(f"\nSelf-check {'PASS' if ok else 'FAIL'} (refs mean {ref_mean:.1f}, want >=80)")
        return 0 if ok else 1


    if not sample_rows:
        return 0
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
