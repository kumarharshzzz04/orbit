# docs/ML.md - Exoplanet Intelligence Pipeline (Owner: C)

Two honest model families so the agent debate has something real to improve:
a classical baseline (GBM) and a 1D CNN, both scored by ONE evaluation harness on
ONE frozen split. Precedent: NASA ExoMiner validated 301+ exoplanets with deep
learning on Kepler photometry - we aim for a credible demo model, not SOTA.

---

## Status (2026-10-25, Member C)

| Gate | State |
|---|---|
| CP-1 data | **Stub**: 1,500 deterministic targets cached. **Live**: KOI table + 12 real MAST targets cached end-to-end (same fingerprint whether fetched sequentially or with 3 workers); full 1,500-target live cache not downloaded yet (network budget). |
| CP-1 baseline | **Working**: F1 0.837, AUC 0.899, accuracy 0.853 on the frozen stub test split (n=224; primary n=191). |
| CP-2 CNN | **Working**: F1 0.821, AUC 0.879, early-stopped at epoch 14/20. Honest negative result vs the champion. |
| CP-2 challenger | **Working**: vetting-feature GBM F1 0.930, AUC 0.983 -> clears the documented gate. Class-weight F1 0.826 and augmented CNN F1 0.830 both fail the F1 bar. |
| CP-2 gate | ML emits PENDING, registry-shaped `run_record.json`; `services/registry.promote()` (Member B) is still the only decision point. |
| FREEZE | Fresh rebuild reproduces dataset fingerprint `ee1f7e04226f8e7b0ca68b3bd4dd8527877bac17` and split fingerprint `303b6081ebb5002449fae5de31b30f5adb78a732`; full live re-run pending. |

> **Numbers above are stub-mode synthetic data.** They prove the pipeline, not
> Kepler performance. Live-data numbers will be lower and must be reported from
> `artifacts/*/metrics.json`, never from this table.

## What exists

```
backend/ml_sandbox/
  labels.py        KOI cumulative TAP query + cached CSV + label normalization
  preprocess.py    deterministic clip/detrend/fold/bin + transit diagnostics
  stub.py          offline synthetic KOI population + light-curve generator
  cache.py         per-target .npz cache, content hashes, packed fast path, manifest
  splits.py        host-grouped 70/15/15 split, frozen manifest, leakage guard
  dataset.py       verified load, split slicing, JSON artifact writer
  features.py      12 catalog features + 2 fold-derived vetting features
  evaluate.py      one metrics harness, candidate handling, threshold selection
  models/          baseline.py (sklearn GBM), cnn.py (PyTorch 1D CNN)
  train.py         CLI: train + evaluate + registry-shaped run record
  build_cache.py   CLI: build/resume the cache (stub or live)
backend/tests/     59 tests: preprocessing, splits/leakage, metrics, cache, CLI, CNN
runs/              champion + challenger configs (stub and live)
```

## Run it

```bash
cd backend
pip install -r requirements.txt          # CPU torch included
python -m ml_sandbox.build_cache --mode stub --targets 1500
python -m ml_sandbox.train --config ../runs/baseline_v1.json --out ../artifacts/baseline_v1
python -m ml_sandbox.train --config ../runs/cnn_v1.json --out ../artifacts/cnn_v1
python -m pytest -q
```

Every training command ends with exactly one JSON line on stdout:

```json
{"ok": true, "metrics": {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "roc_auc": 0.0},
 "artifact": "artifacts/<run_id>/"}
```

Progress lines go to stderr as `ORBIT_PROGRESS {...}` and to `progress.jsonl`; a
crash exits non-zero and still prints `{"ok": false, "error": "..."}` last. The
backend can therefore spawn this as a subprocess without parsing human logs.

## Data plan

| Item | Decision |
|---|---|
| Labels | NASA Exoplanet Archive KOI cumulative: CONFIRMED + CANDIDATE vs FALSE POSITIVE |
| Signals | MAST Kepler long-cadence PDCSAP (lightkurve). TESS not implemented yet. |
| Volume | 1,500-2,000 targets; live KOI table has 9,564 usable rows today |
| Split | Grouped by HOST STAR, 70/15/15, frozen to `data/<mode>/splits/v1.json` + fingerprint |
| Unit | 400-bin folded flux vector + 14 engineered features (12 catalog, 2 fold-derived) |

Primary metric treats CONFIRMED vs FALSE POSITIVE as truth (CANDIDATE labels are
uncertain); candidate-inclusive numbers are reported separately in every artifact.

## Data modes

**stub** (default, offline, deterministic): 1,500 synthetic KOIs over 1,112 host
stars, 360 d baseline at Kepler cadence, two data gaps, stellar variability, red +
white noise, outliers. False positives are eclipsing binaries: unequal odd/even
depths and deep secondary eclipses. Builds in ~12 s on a laptop.

**live** (network): KOI TAP query then lightkurve/MAST downloads, resumable and
per-target. Targets that share a host star reuse one download (KOI rows are
planets, not stars), which avoids concurrent FITS writes and wasted bandwidth.
Failed downloads are recorded in `manifest.json.skipped` instead of killing the
build. Requires the optional stack:

```bash
cd backend
pip install -r requirements-astro.txt
# --workers uses separate PROCESSES (astroquery is not thread-safe)
python -m ml_sandbox.build_cache --mode live --targets 1500 --workers 3
python -m ml_sandbox.train --config ../runs/baseline_live.json --out ../artifacts/live-baseline
```

Measured on the dev network (2026-10-25, 12 targets): 546 s sequential vs
186 s with `--workers 3`, and both builds produced the identical dataset
fingerprint `9abe459480d07159bf305622110f8f61d8f4cc19`. A warm-cache rebuild
with host-deduplicated downloads reproduced that fingerprint in 22 s. A
1,500-target live cache
is therefore roughly 6-7 hours at 3 workers (~20 s/target effective); a
300-target demo subset is roughly 75-90 minutes. Plan the download budget
accordingly, or use the 300-target fallback from the risk register.

**Do not use threads for MAST.** A thread-pool attempt closed shared stdout and
failed 25/40 downloads with `I/O operation on closed file`; process isolation is
the tested path. The CLI defaults to one worker; pass `--workers 3` explicitly
from the standalone command, never from inside the API process.

Live smoke test on 2026-10-25 (two real Kepler targets; all 12 cached targets
produced finite folds and features):

| Target | Catalog depth | Measured depth | Measured SNR | Notes |
|---|---|---|---|---|
| K00001.01 (Kepler-1 b) | 14,231 ppm | 10,064 ppm | 3,818 | deep transit recovered |
| K00752.01 (Kepler-227 b) | 616 ppm | 441 ppm | 29 | shallow transit recovered |

The ~30% depth attenuation is Savitzky-Golay detrending plus long-cadence sampling;
the catalog depth is what the baseline uses, and the vetting features are ratios so
the attenuation largely cancels.

## Preprocessing (pure functions, cached, boring on purpose)

`lightkurve` PDCSAP -> drop NaNs -> divide by median (relative flux) -> rolling-
median sigma clip (6 sigma, with points shallower than 1.5x the catalog depth
protected so real transits survive) -> Savitzky-Golay detrend (5-day window,
order 3) -> normalize median to 1 -> fold at KOI period/t0 -> average into 400
phase bins (empty bins = continuum 1.0) -> `.npz` + feature vector.

The cache stores **content hashes**, not file bytes: `.npz` zip timestamps differ
between rebuilds. `dataset_fingerprint` hashes sorted `(id, host, label,
disposition, content_sha1)` plus the feature schema and `n_bins`. Training verifies
the fingerprint and either the packed matrix hash or every per-target hash before
fitting. `packed.npz` is a verified fast path: 1,500 targets load in ~0.03 s.

## Frozen splits

`freeze_split()` assigns whole host stars in a stable hash order, greedily matching
70/15/15 target shares, then writes `data/<mode>/splits/<version>.json` with a
fingerprint over `(target, host, split) + dataset_fingerprint + seed`.

- It **never overwrites** an existing split. A changed dataset, new targets, a
  missing target or a hand-edited file raises `FrozenSplitError`.
- Build the full cache **before the first training run**. To change the dataset
  later, bump `data.split_version` deliberately (e.g. `v2`) and re-run all
  champions/challengers on it.
- Same-star leakage is unit-tested. The same test is the Skeptic's evidence.

## Models

| Model config | Family | Input | Verified stub result |
|---|---|---|---|
| `runs/baseline_v1.json` | GradientBoosting (sklearn) | 12 catalog features | F1 **0.837**, AUC 0.899 |
| `runs/cnn_v1.json` | 1D CNN (PyTorch CPU) | 400-bin flux | F1 **0.821**, AUC 0.879 |
| `runs/challenger_vetting_features.json` | GBM | 14 features | F1 **0.930**, AUC 0.983 (KEEP candidate) |
| `runs/challenger_class_weight.json` | GBM, balanced weights | 12 features | F1 0.826 (REJECT: F1 below champion) |
| `runs/challenger_cnn_augmented.json` | CNN + phase roll/noise | 400-bin flux | F1 0.830 (REJECT: F1 below champion) |

CNN architecture (docs plan): Conv1d(32)-pool-Conv1d(64)-pool-Conv1d(96)-global
avg pool-dropout(0.3)-FC(64)-1 logit. 64,033 parameters with the default config.
Input transform is fixed: `((flux - 1.0) * 100).clip(-5, 5)`. Training uses
BCEWithLogitsLoss with optional `pos_weight`, Adam, early stopping on validation
F1, a `max_train_seconds` budget, and a fixed thread count for deterministic CPU
replays. Full stub CNN run: ~10 s.

`run_record.json` contains `config_hash`, `seed`, `git_commit`, `git_dirty`,
`dataset_fingerprint`, `split_fingerprint`, the five primary metrics, artifact
path, `verdict: "PENDING"`, `diagnosis: null`, plus the full effective config.
`replayable` is true only when the git tree is clean and all hashes are present.
**Commit before producing demo artifacts** or the gate will rightly call the run
not replayable.

## Metrics and the gate

accuracy, precision, recall, F1, ROC-AUC + confusion matrix on the same frozen test
split. The decision threshold is chosen on validation (F1 sweep) and then frozen;
`training.threshold_selection = "fixed"` uses `training.threshold` instead.

Promotion rule (Member B, `services/registry.py`):

```
challenger.f1 > champion.f1 + margin  AND  challenger.roc_auc >= champion.roc_auc - 1e-9
AND challenger.replayable
```

The ML sandbox does not implement or override this gate. Failures stay as REJECT
rows with the Evaluator's diagnosis - negative results are assets.

## Gotchas / limitations (read before touching ML)

1. **Full live cache is not downloaded.** The code path is tested end-to-end on
   12 real MAST targets; 1,500 live downloads are bandwidth-bound (est. 6-7 h at
   3 workers). Stub is the demo fallback; 300 targets is the realistic live cap.
2. **TESS is not implemented.** Kepler is BKJD; mixing in TESS BTJD without an
   epoch conversion would silently destroy the fold. Do not add TESS during the
   sprint.
3. **Period-error augmentation is not implemented.** It needs raw per-target time
   series; the cache stores folded vectors only. Phase-roll augmentation is
   implemented and did not beat the GBM.
4. **The CNN loses to the GBM on stub data.** That is a real measured negative
   result, not a bug to hide. Do not architecture-golf past CP-2.
5. **Measured depths are attenuated** by detrending and long-cadence sampling
   (~30% on the live smoke targets). Catalog features are unaffected; vetting
   ratios are relatively robust.
6. **CANDIDATE labels are uncertain.** Never quote candidate-inclusive numbers as
   primary.
7. **Never regenerate a frozen split.** Bump `data.split_version` only after the
   cache is complete.
8. **Never hand-edit `packed.npz` or `manifest.json`.** Both fail verification;
   rebuild the cache instead.
9. **The archive column is `koi_srad`, not `koi_sradius`.** This bit us once in a
   TAP query.
10. **`git_dirty` disables replayability.** Commit first, then run the demo
    artifacts. `git status` includes untracked source files on purpose.
11. **One cache builder at a time.** There is no file lock; two concurrent builds
   in the same data root can interleave manifest writes.
12. **CI workflow is not active yet.** `ci.yml` at the repo root is B's to install
    at `.github/workflows/ci.yml` once `backend/app/` and `frontend/` exist. The ML
    test suite is ready for that workflow's `test` job.

## Definition of done for the ML handoff to B

- [x] `python -m ml_sandbox.train ...` prints one JSON line and exits non-zero on failure
- [x] `run_record.json` matches the registry row contract (verdict PENDING)
- [x] Same config + same dataset fingerprint -> identical metrics (tested)
- [x] Host-star leakage test and frozen-split refusal test
- [x] Baseline + CNN trained and scored by the same harness
- [ ] Full live cache downloaded and re-scored (network budget)
- [ ] B inserts `run_record.json` rows and applies `promote()`
- [ ] FREEZE replay on a second machine (same fingerprint, same metrics)
