"""Seed demo segments: split GeoJSON lines into scored stretches (RNG seed 42)."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common import clock, geo, repo, scoring


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed demo road segments")
    parser.add_argument("--geojson", required=True)
    parser.add_argument("--ward", default="WARD-05")
    parser.add_argument("--stretch-m", type=float, default=250.0)
    parser.add_argument("--importance", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _stretches(path: str, target_m: float) -> list[tuple[str, list[list[float]]]]:
    with open(path) as handle:
        data = json.load(handle)
    out: list[tuple[str, list[list[float]]]] = []
    for i, feature in enumerate(data.get("features", [])):
        geometry = feature.get("geometry", {})
        if geometry.get("type") != "LineString":
            continue
        name = feature.get("properties", {}).get("name", f"Road {i + 1}")
        for piece in geo.split_linestring(geometry["coordinates"], target_m):
            out.append((name, piece))
    return out


def main() -> None:
    args = _args()
    rng = random.Random(42)  # noqa: S311 - deterministic demo spread, not crypto
    now = clock.now()
    made: list[dict] = []
    skipped = 0
    counter = 0
    for name, coords in _stretches(args.geojson, args.stretch_m):
        counter += 1
        segment_id = f"SEG-{counter:03d}"
        if repo.get_segment(segment_id) is not None and not args.overwrite:
            skipped += 1
            continue
        importance = args.importance or rng.randint(2, 5)
        dust = rng.choices([0, 1, 2, 3], weights=[2, 3, 4, 4])[0]
        cleaned = None
        if rng.random() >= 0.15:
            cleaned = (now - timedelta(days=rng.randint(1, 14))).replace(microsecond=0)
            cleaned = cleaned.isoformat().replace("+00:00", "Z")
        base = {
            "importance": importance,
            "cadenceEstDays": 8.0,
            "lastCleanedAt": cleaned,
            "lastDustLevel": dust,
        }
        result = scoring.score_segment(
            base,
            inspector_rating=dust,
            weather=None,
            debris=False,
            now=clock.utc_now_iso(),
        )
        item = {
            "segmentId": segment_id,
            "roadName": name,
            "corridorId": f"{args.ward}-C1",
            "wardId": args.ward,
            "geometry": {"type": "LineString", "coordinates": coords},
            "lengthM": round(geo.linestring_length_m(coords), 1),
            "importance": importance,
            "cadenceEstDays": 8.0,
            "lastCleanedAt": cleaned,
            "lastDustLevel": dust,
            "lastInspectedAt": None,
            "cleaningStatus": result.cleaning_status,
            "priorityScore": result.priority_score,
            "priorityLevel": result.priority_level,
            "priorityBreakdown": {
                "components": result.components,
                "weights": result.weights,
                "inputs": result.inputs,
            },
            "explanation": result.explanation,
            "weatherSnapshot": None,
            "isDemo": True,
            "updatedAt": clock.utc_now_iso(),
        }
        if not args.dry_run:
            repo.put_segment(item)
        made.append(item)
    levels: dict[str, int] = {}
    for item in made:
        levels[item["priorityLevel"]] = levels.get(item["priorityLevel"], 0) + 1
    print(
        f"segments: {len(made)} skipped={skipped} levels={levels} "
        f"dry_run={args.dry_run}"
    )
    if skipped > 0:
        print("WARNING: skipped existing items (may lack fields); use --overwrite.")
    top = sorted(made, key=lambda s: s["priorityScore"], reverse=True)[:5]
    for item in top:
        print(
            f"{item['segmentId']} {item['priorityScore']:.3f} "
            f"{item['priorityLevel']}: {item['explanation']}"
        )


if __name__ == "__main__":
    main()
