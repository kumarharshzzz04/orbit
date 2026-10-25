# ORBIT

**Self-improving AI research system for space science.** Six agents read the literature,
propose a change to the current champion model, attack each other's reasoning, run a real
experiment on NASA exoplanet data, and keep only what survives an independent evaluation
gate. Negative results are stored with a diagnosis — the registry is the memory.

First mission: **exoplanet detection** on Kepler light curves (KOI labels + MAST PDCSAP flux).

> ORBIT does not discover planets. It discovers better ways to look for them, and it can prove it.

Read [AGENTS.md](AGENTS.md) first. It is the operating manual for humans and AI agents.

---

## For judges: what is proven, and where to check it

Every number below comes from a command or artifact in this repository, on public NASA
data. None of it is a slide claim.

| Claim | Evidence | Check it |
|---|---|---|
| **Real data, fingerprinted** | 9,564 KOI labels from the NASA Exoplanet Archive (TAP fetch writes SHA-1 + timestamp beside the CSV), 297 live Kepler light curves from MAST, frozen host-grouped split with its own fingerprint | [docs/ML.md](docs/ML.md) §Data, `ml_sandbox/splits.py` |
| **Scale checked on the whole catalog** | 9,564 targets / 8,214 host stars, host-grouped 5-fold, primary truth: **F1 0.883 ± 0.017, AUC 0.971 ± 0.005** | [runs/evidence/catalog_full_cv.json](runs/evidence/catalog_full_cv.json), `python -m ml_sandbox.catalog_cv` |
| **Honest generalization number** | Folded-pixel champion on unseen hosts: **F1 0.801 ± 0.036, AUC 0.934 ± 0.030**. The 0.933 frozen-split figure is only ever quoted beside it | [docs/ML.md](docs/ML.md) §Second estimate |
| **Errors diagnosed, not hidden** | 48% of out-of-fold false positives (12/25) carry the archive's centroid-blend flag; both frozen-split FPs are confirmed blends at 8.52″ and 3.69″ | [docs/ML.md](docs/ML.md) §pixel-level diagnostic |
| **A gate that rejects** | Vetting-feature, class-weight and CNN challengers were all **REJECT** against the champion, with diagnoses; `promote()` is the only thing allowed to change the champion | [runs/](runs), [AGENTS.md](AGENTS.md) §3.2 |
| **Pre-registered, not post-hoc** | The Platt-calibration challenger (H-003) was written **before** split v2 existed and has never been scored on v1 test rows | [runs/challenger_calibrated_live.json](runs/challenger_calibrated_live.json) |
| **Reproducible by construction** | Every run records config hash, seed, git commit, dataset and split fingerprints; 73 tests cover leakage, determinism, the CLI contract and replay | `pytest -q` |
| **NVIDIA GPU path, measured** | CUDA CNN: 11.97 s → 2.36 s training (**5.1×**), identical F1; CPU stays default so existing hashes replay | [docs/ML.md](docs/ML.md) §NVIDIA GPU path |

### The scale question, answered with a number

"300 targets" is the wrong thing to defend, so we ran the same pipeline over the entire
Kepler Objects of Interest table — no downloads, catalog features only:

| Training data | 5-fold F1 | 5-fold AUC | Primary rows |
|---|---|---|---|
| 297 live light curves | 0.801 ± 0.036 | 0.934 ± 0.030 | 234 out-of-fold |
| **full KOI catalog (9,564)** | **0.883 ± 0.017** | **0.971 ± 0.005** | 7,587 |

32× more data shrinks the confidence interval by 3×. That precision is the result — not a
new detector. Catalog features are transit-fit parameters and partly correlated with the
archive's own disposition, so this is a scale and protocol check. The independent-evidence
claim stays with folded pixels: **0.80 F1 on unseen host stars**, which is what the system
would actually have to rely on for a new target. Both caveats are written into the doc, not
buried.

### What is real today, and what is not

The ML sandbox is real, measured and reproducible. The agent loop, API and UI are the next
build — nothing in this README pretends they exist yet.

| Module | Owner | State |
|---|---|---|
| ML sandbox + eval harness (`backend/ml_sandbox/`) | C | **Evidence complete** — 297 live targets on a frozen split, 1,500-target stub cache, 900-target live cache building (resumable), 73 tests, full-catalog scale check |
| FastAPI app, SQLite, registry, CI (`backend/app/`) | B | Not started — start at [docs/BACKEND.md](docs/BACKEND.md) |
| Agent orchestrator + prompts (`backend/app/services/`) | A | Not started — start at [docs/AGENTS_SYSTEM.md](docs/AGENTS_SYSTEM.md) |
| React mission control (`frontend/`) | D | Not started — start at [docs/FRONTEND.md](docs/FRONTEND.md) |

`ci.yml` at the repo root is the workflow B installs at `.github/workflows/ci.yml` once
`backend/app/` and `frontend/` exist. It is intentionally not active yet — it would only be red.

### The limitations, stated by us first

- **0.933 is one 32-row draw.** Cross-validation over all 297 targets gives 0.80 F1. Anyone
  quoting 0.933 alone is quoting the split, not the model.
- **The residual error is pixel-level, not photometric.** 12 of 25 out-of-fold false
  positives are blends that need centroid motion or difference imaging, which this pipeline
  does not ingest. More of the same photons will narrow intervals, not lift F1.
- **CANDIDATE labels are excluded from the primary metric** (2,000+ uncertain rows) and
  reported separately instead of being counted as positives.
- **Kepler only.** TESS is not implemented.
- **The sample is 297 light curves, not 900 and not 9,564.** The catalog check covers the
  archive's scale; the light-curve cache is a resumable subset chosen by download budget,
  and the README says so rather than implying otherwise.

## Start here

Everyone should be able to run the ML pipeline and its tests on CPU without network:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m ml_sandbox.build_cache --mode stub --targets 1500
python -m pytest -q
```

Then follow your module:

| Role | Read | Build against | Done when |
|---|---|---|---|
| A (agents) | `docs/AGENTS_SYSTEM.md` | `docs/fixtures/proposal.example.json` | A mission produces a proposal, Skeptic verdict, Experimenter run and Evaluator verdict |
| B (backend) | `docs/BACKEND.md` | `docs/fixtures/registry_rows.example.json` | `run_record.json` is inserted append-only and `promote()` changes the champion |
| D (frontend) | `docs/FRONTEND.md` | `docs/fixtures/ws_events.jsonl` | Replaying the fixture renders the debate, leaderboard and KEEP chip; then swap in the real socket |
| C (ML) | `docs/ML.md` | `runs/*.json` | Live cache scored on the frozen split; tuning stays validation-only |

Full handoff block with commands and traps: [HANDOVER.md](HANDOVER.md). The shared mock
stream, registry rows and proposal live under [docs/fixtures](docs/fixtures).

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
    fixtures/               WS stream, registry rows, one-change proposal
  ORBIT_Hackathon_Master_Plan.pdf
  backend/
    ml_sandbox/              # owned by C - data, models, evaluation
    tests/                   # schema/gate/replay/ML tests
    requirements.txt
  frontend/                  # owned by D (not created yet)
  runs/                      # experiment configs + committed evidence reports
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

# 4. uncertainty on a scored split (grouped bootstrap over host stars)
python -m ml_sandbox.stability --predictions ../artifacts/baseline_live/predictions.csv

# 5. full-catalog scale check (needs a cached KOI table; writes runs/evidence/)
python -m ml_sandbox.catalog_cv

# 6. tests (leakage, determinism, CLI contract, replay, gate, stability) - 73 tests
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

## Live NASA data

Same pipeline with `--mode live`; it needs the optional astronomy stack:

```bash
cd backend
pip install -r requirements-astro.txt
python -m ml_sandbox.build_cache --mode live --targets 900 --workers 3
python -m ml_sandbox.train --config ../runs/baseline_live.json --out ../artifacts/live-baseline
```

The frozen live split is 297 real Kepler targets (300 requested, 3 skipped). Champion:
F1 0.933 / AUC 0.984 on the 32-row primary test split, **0.801 / 0.934 cross-validated over
all 297** — full numbers and caveats in [docs/ML.md](docs/ML.md). A 900-target cache is
building with a resumable manifest; `bash data/resume.sh` restarts it idempotently and
refuses to start a second downloader.

Downloads are process-isolated (`--workers 3`): astroquery is not thread-safe. Targets
sharing a host star reuse one download, since KOI rows are planets rather than stars.
Measured ~4.5 targets/min on this machine, so the 900-target expansion is a budget
exercise, not a method one.

## Reproducing the headline evidence

```bash
cd backend
pytest -q                                    # 73 tests, no network
python -m ml_sandbox.catalog_cv              # 9,564-row scale check -> runs/evidence/
python -m ml_sandbox.train --config ../runs/baseline_live.json --out ../artifacts/live-baseline
```

The committed report carries its KOI CSV SHA-1 and the commit it ran at, so a changed
number is traceable rather than arguable.

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
