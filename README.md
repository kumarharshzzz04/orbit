# ORBIT

**Self-improving AI research system for space science.** Six agents read the literature,
propose a change to the current champion model, attack each other's reasoning, run a real
experiment on NASA exoplanet data, and keep only what survives an independent evaluation
gate. Negative results are stored with a diagnosis — the registry is the memory.

First mission: **exoplanet detection** on Kepler light curves (KOI labels + MAST PDCSAP flux).

> ORBIT does not discover planets. It discovers better ways to look for them, and it can prove it.

Read [AGENTS.md](AGENTS.md) first. It is the operating manual for humans and AI agents.

---

## Current state

| Module | Owner | State |
|---|---|---|
| ML sandbox + eval harness (`backend/ml_sandbox/`) | C | **Working** — stub cache 1,500, GBM F1 0.837, CNN F1 0.821, vetting challenger F1 0.930; live KOI+MAST path smoke-tested |
| FastAPI app, SQLite, registry, CI (`backend/app/`) | B | Not started |
| Agent orchestrator + prompts (`backend/app/services/`) | A | Not started |
| React mission control (`frontend/`) | D | Not started |

`ci.yml` at the repo root is the workflow B installs at `.github/workflows/ci.yml` once
`backend/app/` and `frontend/` exist. It is intentionally not active yet — it would only be red.

## Repository layout

```
orbit/
  README.md                 this file
  AGENTS.md                 coordination protocol - read first
  PROGRESS.md               append-only work log
  HANDOVER.md               module handover template
  ci.yml                    GitHub Actions workflow (B activates it)
  docs/                     module briefs + agent specs
    ML.md BACKEND.md FRONTEND.md AGENTS_SYSTEM.md
  ORBIT_Hackathon_Master_Plan.pdf
  backend/
    ml_sandbox/              # owned by C - data, models, evaluation
    tests/                   # schema/gate/replay/ML tests
    requirements.txt
  frontend/                  # owned by D (not created yet)
  runs/                      # experiment configs (JSON)
  data/                      # cached labels + light curves (git-ignored)
  artifacts/                 # run outputs: metrics, model, run_record.json (git-ignored)
```

## 90-second ML runbook (works offline, CPU only)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. build a deterministic synthetic cache (no network; DATA_MODE=stub)
python -m ml_sandbox.build_cache --mode stub --targets 1500

# 2. train the classical champion
python -m ml_sandbox.train --config ../runs/baseline_v1.json --out ../artifacts/baseline_v1

# 3. train the CNN challenger
python -m ml_sandbox.train --config ../runs/cnn_v1.json --out ../artifacts/cnn_v1

# 4. tests (leakage, determinism, CLI contract, replay) - 59 tests
pytest -q
```

Verified on 2026-10-25: baseline F1 0.837 / AUC 0.899, CNN F1 0.821 / AUC 0.879,
vetting-feature challenger F1 0.930 / AUC 0.983 on frozen stub split `v1`. These
are synthetic-data numbers; they prove the pipeline, not Kepler performance.

Every training command ends with one JSON line on stdout:

```json
{"ok": true, "metrics": {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "roc_auc": 0.0}, "artifact": "artifacts/<run_id>/"}
```

A crash exits non-zero and still prints `{"ok": false, "error": "..."}` as the last line.
Progress lines go to stderr as `ORBIT_PROGRESS {...}` so the backend can stream them over
WebSocket without parsing the result contract.

Live data (NASA Exoplanet Archive + MAST) is the same pipeline with `--mode live`; it needs
the optional astronomy stack:

```bash
cd backend
pip install -r requirements-astro.txt
python -m ml_sandbox.build_cache --mode live --targets 1500 --workers 3
python -m ml_sandbox.train --config ../runs/baseline_live.json --out ../artifacts/live-baseline
```

The live path was smoke-tested on 12 real Kepler targets. Downloads are
process-isolated (`--workers 3`): astroquery is not thread-safe. Targets sharing a
host star reuse one download, since KOI rows are planets rather than stars.
Measured ~20s per target effective; a 300-target demo subset is ~75-90 minutes, so
plan the download budget (the full 1,500 is ~6-7 hours).

## Contracts

The three cross-module contracts live in [AGENTS.md](AGENTS.md) §3: the WebSocket event
schema, the append-only experiment registry row, and the ML sandbox CLI. The ML sandbox
emits a registry-shaped `run_record.json` for every run — `verdict` starts `PENDING`, and
the backend's `promote()` is the only thing allowed to change the champion.

## Docs

- [docs/ML.md](docs/ML.md) — data plan, preprocessing, models, gate, gotchas
- [docs/BACKEND.md](docs/BACKEND.md) — FastAPI layout, API surface, SQLite schema
- [docs/FRONTEND.md](docs/FRONTEND.md) — mission control panels and state rules
- [docs/AGENTS_SYSTEM.md](docs/AGENTS_SYSTEM.md) — the six-agent loop and prompts
- [ORBIT_Hackathon_Master_Plan.pdf](ORBIT_Hackathon_Master_Plan.pdf) — the full build plan
