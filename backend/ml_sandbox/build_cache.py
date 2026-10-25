"""Build the cached KOI dataset: ``python -m ml_sandbox.build_cache``.

Stub mode is fully offline and deterministic. Live mode downloads the KOI table
from the NASA Exoplanet Archive and Kepler PDCSAP light curves from MAST; it
resumes from whatever is already cached and records failed targets instead of
aborting the whole build.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any

from . import cache, labels, paths, stub

LOG = logging.getLogger("orbit.ml.cache")


def _progress(event: dict[str, Any]) -> None:
    payload = dict(event)
    done = int(payload.pop("done", 0))
    total = int(payload.pop("total", 0))
    payload["done"] = done
    payload["total"] = total
    payload["percent"] = round(100.0 * done / max(total, 1), 1)
    print(
        "ORBIT_PROGRESS " + json.dumps(payload, sort_keys=True),
        file=sys.stderr,
        flush=True,
    )


def _load_label_frame(args: argparse.Namespace, root: Path) -> tuple[Any, str]:
    labels_path = root / "koi.csv"
    root.mkdir(parents=True, exist_ok=True)
    if args.mode == "stub":
        frame = stub.make_stub_labels(n_targets=args.targets, seed=args.seed)
        frame.to_csv(labels_path, index=False)
        return frame, str(labels_path)

    frame = labels.load_koi_labels(labels_path, refresh=args.refresh_labels)
    LOG.info("KOI table has %d usable labelled targets", len(frame))
    if len(frame) > args.targets:
        frame = (
            frame.sample(n=args.targets, random_state=args.seed)
            .sort_values("target_id")
            .reset_index(drop=True)
        )
    return frame, str(labels_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ml_sandbox.build_cache",
        description="Cache folded light curves and features for ORBIT.",
    )
    parser.add_argument(
        "--mode",
        choices=("stub", "live"),
        default=os.environ.get("DATA_MODE", "stub"),
        help="stub = deterministic synthetic data (offline); live = NASA/MAST",
    )
    parser.add_argument(
        "--targets",
        type=int,
        default=1500,
        help="target count (stub) or maximum live targets to download",
    )
    parser.add_argument("--seed", type=int, default=42, help="data/build seed")
    parser.add_argument("--n-bins", type=int, default=400, help="phase bins")
    parser.add_argument(
        "--root",
        default=None,
        help="data root (default: data/<mode>, or ORBIT_DATA_DIR/<mode>)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="regenerate every target, even if cached",
    )
    parser.add_argument(
        "--refresh-labels",
        action="store_true",
        help="re-download the KOI table (live mode only)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "process-isolated live downloads, 1-8. Use the standalone CLI; "
            "do not enable from inside the API process"
        ),
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.targets < 10:
        print(json.dumps({"ok": False, "error": "--targets must be >= 10"}))
        return 2
    if not args.quiet:
        logging.basicConfig(
            level=logging.INFO,
            stream=sys.stderr,
            format="%(asctime)s %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
        )

    root = (
        Path(args.root).expanduser().resolve()
        if args.root
        else paths.mode_root(args.mode)
    )
    try:
        frame, labels_path = _load_label_frame(args, root)
        report = cache.build_cache(
            frame,
            mode=args.mode,
            cache_dir=root / "cache",
            n_bins=args.n_bins,
            seed=args.seed,
            rebuild=args.rebuild,
            strict=args.mode == "stub",
            workers=args.workers,
            progress=_progress,
        )
    except Exception as exc:  # noqa: BLE001 - contract: always end with JSON
        traceback.print_exc(file=sys.stderr)
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                sort_keys=True,
            ),
            flush=True,
        )
        return 1

    summary = report.as_dict()
    summary.update(
        {
            "labels": labels_path,
            "n_labels": int(len(frame)),
            "n_bins": args.n_bins,
            "seed": args.seed,
            "workers": max(1, min(int(args.workers), 8)),
        }
    )
    try:
        (root / "cache_build.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except OSError as exc:  # pragma: no cover - disk failure path
        LOG.warning("could not write cache_build.json: %s", exc)

    LOG.info(
        "cached %d targets (%d new, %d reused, %d skipped) in %.1fs",
        len(frame),
        report.new,
        report.reused,
        report.skipped,
        report.seconds,
    )
    LOG.info("dataset fingerprint %s", report.dataset_fingerprint)
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
