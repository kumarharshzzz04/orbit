"""Seed the experiment registry from ML sandbox run records.

The ML side writes a registry-shaped `run_record.json` per run. This script is the
handoff: it bootstraps the champion and then puts every challenger through the
gate, so the registry ends up holding the same verdicts the docs report.

`artifacts/` is git-ignored, so this runs against a local checkout that has the
runs on disk. Nothing is edited afterwards - promotion only appends.

Usage
-----
    python scripts/seed_registry.py --db ../data/orbit.db
    python scripts/seed_registry.py --dry-run

Exit code is 0 when the seeding completed, including when the gate rejects a
challenger. A rejection is a result, not an error.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlmodel import Session  # noqa: E402

from app.db.config import get_engine, init_db  # noqa: E402
from app.db.models import Hypothesis, Mission, MissionStatus  # noqa: E402
from app.services import registry  # noqa: E402

DEFAULT_ARTIFACTS = BACKEND.parent / "artifacts"
DEFAULT_CHAMPION = "baseline_live_v2"
CHALLENGERS = (
    "challenger_class_weight_live_v2",
    "challenger_calibrated_live_v2",
    "challenger_vetting_features_live_v2",
    "cnn_live_v2",
    "challenger_hist_live_v2",
)


SEED_MISSION = "mission-seed-v2"


def ensure_mission(session: Session) -> None:
    """Create the seed mission once so hypothesis rows have a valid parent."""
    if session.get(Mission, SEED_MISSION) is not None:
        return
    session.add(
        Mission(
            id=SEED_MISSION,
            question=(
                "On 893 Kepler objects of interest, does any single declared change "
                "beat the frozen-pixel champion under the F1 + AUC gate?"
            ),
            budget_rounds=2,
            current_round=1,
            status=MissionStatus.COMPLETED,
        )
    )
    session.commit()


def ensure_hypothesis(session: Session, record: dict) -> None:
    """The registry requires a hypotheses row before an experiment can reference it."""
    hypothesis_id = record.get("hypothesis_id")
    if not hypothesis_id or session.get(Hypothesis, hypothesis_id) is not None:
        return
    session.add(
        Hypothesis(
            id=hypothesis_id,
            mission_id=SEED_MISSION,
            proposal_json={
                "hypothesis_id": hypothesis_id,
                "source_run": record["id"],
                "config_hash": record.get("config_hash"),
                "notes": record.get("config", {}).get("notes"),
            },
        )
    )
    session.commit()


def load(artifacts: pathlib.Path, run_id: str) -> dict:
    path = artifacts / run_id / "run_record.json"
    if not path.exists():
        raise SystemExit(f"missing run record: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the ORBIT registry")
    parser.add_argument("--db", default=str(BACKEND.parent / "data" / "orbit.db"))
    parser.add_argument("--artifacts", default=str(DEFAULT_ARTIFACTS))
    parser.add_argument("--champion", default=DEFAULT_CHAMPION)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    artifacts = pathlib.Path(args.artifacts).resolve()
    db_path = pathlib.Path(args.db).resolve()

    champion_record = load(artifacts, args.champion)
    challenger_records = []
    for run_id in CHALLENGERS:
        path = artifacts / run_id / "run_record.json"
        if path.exists():
            challenger_records.append(json.loads(path.read_text(encoding="utf-8")))
        else:
            print(f"skip {run_id}: no run record")

    if args.dry_run:
        print(f"db       {db_path}")
        print(
            f"champion {champion_record['id']} F1 {champion_record['metrics']['f1']:.4f}"
        )
        for record in challenger_records:
            print(
                f"challenger {record['id']} F1 {record['metrics']['f1']:.4f} "
                f"replayable={record.get('replayable')}"
            )
        return 0

    init_db(db_path)
    engine = get_engine()

    with Session(engine) as session:
        ensure_mission(session)
    for record in [champion_record, *challenger_records]:
        with Session(engine) as session:
            ensure_hypothesis(session, record)

    with Session(engine) as session:
        try:
            kept = registry.bootstrap_champion(session, champion_record)
            print(f"champion  {kept.id}")
        except RuntimeError as error:
            print(f"champion  not bootstrapped: {error}")

    for record in challenger_records:
        with Session(engine) as session:
            try:
                registry.insert_experiment(session, record)
                session.commit()
            except Exception as error:  # already present is not a failure
                session.rollback()
                print(f"pending   {record['id']} skipped: {error}")
                continue

        with Session(engine) as session:
            verdict, rationale = registry.promote(session, record["id"])
            print(f"{verdict.value:9s} {record['id']}: {rationale}")

    with Session(engine) as session:
        champion = registry.get_champion(session)
        print(f"final champion: {champion.id if champion else 'none'}")
        for row in registry.list_experiments(session, limit=20):
            print(f"  {row.verdict.value:8s} {row.id}")
    print(f"db {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
