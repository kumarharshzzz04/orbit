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
| ML sandbox + eval harness (`backend/ml_sandbox/`) | C | **Working** — stub + live data paths, frozen grouped splits, GBM and 1D-CNN, replayable run records |
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

# 4. tests (leakage, determinism, CLI contract, replay)
pytest -q
```

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
pip install -r requirements-astro.txt
python -m ml_sandbox.build_cache --mode live --targets 1500
```

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
