# docs/ML.md - Exoplanet Intelligence Pipeline (Owner: C)

Two honest model families so the agent debate has something real to improve:
a classical baseline (GBM) and a 1D CNN, both scored by ONE evaluation harness on
ONE frozen split. Precedent: NASA ExoMiner validated 301+ exoplanets with deep
learning on Kepler photometry - we aim for a credible demo model, not SOTA.

---

## Status (2026-10-25, Member C)

| Gate | State |
|---|---|
| CP-1 data | **Stub**: 1,500 deterministic targets cached. **Live v2**: 893 real Kepler targets cached from a 900-target request (7 skipped, reasons in `cache_build.json`), 8,805 s at 3 workers, dataset `aa1bb5ca...`. **Live v1** (297 targets) is preserved as the historical split. |
| CP-1 baseline | **Working**: stub F1 0.837, AUC 0.899 (n=224). **Live v2** F1 0.9032 (0.8148-0.9706), AUC 0.9740 on 98 primary test rows. **Live v1** F1 0.933 on 32 rows (historical). **0.80 ± 0.04 F1 / 0.934 AUC on host-grouped 5-fold CV** - the CV number is the generalization estimate. |
| CP-2 CNN | **Working**: stub F1 0.821. **Live** F1 0.737, AUC 0.706 - underfits at 208 training rows. Honest negative result. |
| CP-2 challenger | **Stub**: vetting-feature GBM F1 0.930, AUC 0.983 -> clears the gate. **Live v2**: all four challengers REJECT - class-weight 0.8667, pre-registered Platt calibration (H-003) 0.8667, vetting features 0.8485, CNN 0.5918, against a 0.9032 champion. H-003 was falsified, not refitted. |
| CP-2 gate | ML emits PENDING, registry-shaped `run_record.json`; `services/registry.promote()` (Member B) is still the only decision point. |
| FREEZE | Stub rebuild reproduces dataset fingerprint `ee1f7e04226f8e7b0ca68b3bd4dd8527877bac17` and split fingerprint `303b6081ebb5002449fae5de31b30f5adb78a732`. Live v1: dataset `3826e7f3542eca36941d0b73bef04769f443ac0d`, split `d8aa6b9975c56f1cdda7a1c5e1a88d3780175567`, same-config replay reproduced every metric to 16 decimals. Live v2: dataset `aa1bb5ca19a2390cc2f6cf1a6014d100f9b15dfe`, split `7449f8b87a9319d83537246ed1bfbf07a1e2e13b` (frozen once, after the cache completed). |

> **The stub rows are synthetic.** They prove the pipeline, not Kepler
> performance. Every live number below is copied from `artifacts/*/metrics.json`.

## Live results (2026-10-25, real Kepler/MAST data)

297 targets, 294 host stars, frozen live split v1: train 208 / val 45 / test 44
(primary 32 with 14 positives; the other 12 test rows are CANDIDATE and are
scored separately). Same seed, same harness, same threshold rule for all four.

| Run | Config | F1 | AUC | Acc | Prec | Rec | Live verdict |
|---|---|---|---|---|---|---|---|
| champion | `baseline_live` | **0.9333** | 0.9841 | 0.9375 | 0.875 | 1.000 | champion (first row) |
| challenger | `challenger_vetting_features_live` | 0.9333 | **0.9960** | 0.9375 | 0.875 | 1.000 | REJECT: F1 gain 0.0000, gate needs > 0 |
| challenger | `challenger_class_weight_live` | 0.9286 | 0.9802 | 0.9375 | 0.929 | 0.929 | REJECT: F1 -0.0048 |
| challenger | `cnn_live` | 0.7368 | 0.7063 | 0.6875 | 0.583 | 1.000 | REJECT: F1 -0.1965 |

Candidate-inclusive (all 44 test rows, CANDIDATE counted positive): champion
F1 0.8085 / AUC 0.9509; vetting F1 0.8333 / AUC 0.9573; class-weight 0.8261 /
0.9509; CNN 0.7586 / 0.6368.

### Second estimate: host-grouped 5-fold cross-validation

The 32-row test split is one draw. A 5-fold, host-grouped CV over all 297 targets
(no fold assignment touches the frozen split; hyperparameters unchanged; each fold
scored at the threshold already chosen on the original validation split, so no
fold picks its own) gives a better estimate of unseen-host performance:

| Feature set | 5-fold F1 | 5-fold AUC | Pooled out-of-fold F1 (n=234, 89 pos) |
|---|---|---|---|
| `catalog_v1` (champion) | 0.801 ± 0.036 | 0.934 ± 0.030 | 0.800 (120 TN, 25 FP, 13 FN, 76 TP) |
| `vetting_v1` (challenger) | 0.810 ± 0.072 | 0.946 ± 0.037 | 0.810 (118 TN, 27 FP, 10 FN, 79 TP) |

**Read this before quoting 0.933 anywhere.** The frozen test split is easier than
the population: 2 false positives in 32 primary rows versus 25 in 234 out-of-fold
rows. The honest generalization statement is **F1 ≈ 0.80 on unseen host stars**,
and the 0.93 is a property of this particular 32-row draw, not of the model.
The gate still runs on the frozen split - that is its job and changing it now
would be post-hoc - but every slide should show the CV number next to the split
number, or say "0.93 (32-row split; 0.80 cross-validated)".

The rank-quality advantage of the vetting features also shrinks under CV (AUC
0.946 vs 0.937, overlapping intervals) even though the single split showed 0.996
vs 0.984. Another reason the single-split comparison was never decisive.

### Scale check: the full KOI catalog, no downloads

The 297-target cache is a demo subset, not a research dataset. To see what scale
would buy, the same 12 catalog features were trained on the **entire** KOI table
(9,564 usable rows, 8,214 host stars, 4,725 positives of which 2,748 are
CONFIRMED), host-grouped 5-fold CV. Each fold picks its threshold on an inner
validation split, and metrics are scored on primary truth (CONFIRMED vs FALSE
POSITIVE), the same protocol as every other number in this document:

| Training data | 5-fold F1 | 5-fold AUC | Primary rows |
|---|---|---|---|
| 297 light curves, catalog features | 0.801 ± 0.036 | 0.934 ± 0.030 | 234 out-of-fold |
| full KOI table, catalog only | **0.883 ± 0.017** | **0.971 ± 0.005** | 7,587 |

Pooled out-of-fold confusion at per-fold thresholds: 4,517 TN, 322 FP, 321 FN,
2,427 TP (F1 0.883). Reproduce with `python -m ml_sandbox.catalog_cv`; the
committed report is `runs/evidence/catalog_full_cv.json` and carries the KOI CSV hash and
the git commit it ran at.

**Do not read this as 0.883 > 0.801.** Three differences matter:

1. The rows are not the same population. The 297-target sample was drawn for
   light-curve availability; the full table includes the easy, high-SNR
   confirmations that dominate the archive.
2. Catalog features are transit-fit parameters, not independent evidence. Depth,
   radius ratio and SNR are the same quantities the archive's own disposition
   leaned on, so this number measures how well the pipeline *reproduces* a
   well-separated catalog boundary - not how well it would discover a new planet
   from pixels.
3. 32x more rows is why the interval collapses by 3x, and that precision is the
   real result: at this scale the fold-shape features (odd/even, secondary
   eclipse) add nothing over catalog parameters, consistent with the pixel-level
   diagnostic below.

The independent-evidence claim stays with the folded-pixel model, and it stays
at **F1 0.80 on unseen hosts**. What the catalog check proves is scale and
protocol, not a better detector.

An earlier inline version of this check reported 0.835 / 0.923. That run scored
candidate-inclusive rows at a single 0.5 threshold (we reproduced 0.838 / 0.926
on the same out-of-fold predictions), which mixes 2,000 uncertain CANDIDATE
labels into the truth set. It is superseded by the primary-truth table above.

**Recommended next step:** add a `catalog` mode (labels + catalog features, no
MAST downloads) as a first-class training path. Then the pitch can say "validated
on all 9,564 KOIs, with a 900-target light-curve subset for shape diagnostics"
instead of defending a 297-target subset.

### What the residual errors are (pixel-level diagnostic)

The archive publishes pixel-based vetting statistics that a photometry-only
pipeline never sees. One TAP query, cached locally at `data/live/koi_pixel.csv`:

```sql
select kepoi_name, koi_fpflag_nt, koi_fpflag_ss, koi_fpflag_co, koi_fpflag_ec,
       koi_fwm_stat_sig, koi_dicco_msky, koi_dikco_msky, koi_score
from cumulative where koi_disposition in ('CONFIRMED','CANDIDATE','FALSE POSITIVE')
```

Joined against the 25 out-of-fold false positives (234 primary rows):

| Group | n | centroid flag | not-transit-like | stellar eclipse |
|---|---|---|---|---|
| our false positives | 25 | **12 (48%)** | 13 (52%) | 4 (16%) |
| all FP-labelled primaries | 145 | 62 (43%) | 40 (28%) | 64 (44%) |
| CONFIRMED primaries | 89 | 0 (0%) | 0 (0%) | 0 (0%) |

The two frozen-split false positives are both centroid-offset cases:
K03492.01 has an 8.52" difference-image offset, K04641.01 3.69" plus an
ephemeris-match flag. So the earlier "shallow low-SNR" read was incomplete: the
signal really is coming from a nearby source in both cases.

This is the error budget, and it explains why no feature tweak or extra light
curve moved F1. Half the residual error is background blends that are invisible
in folded flux; the rest is not-transit-like noise and stellar variability.

**These flags are not eligible as features.** They are inputs to the archive's own
disposition, so training on them would be circular, would score near-perfectly,
and the Skeptic would rightly veto it. They are used here only to explain errors.
A production system would compute centroid shifts itself from Target Pixel Files.

### Where the ceiling is (data-scaling check)

Before spending the download budget we measured whether F1 is data-limited.
Champion and challenger were retrained on stratified subsets of the **train**
split only (three seeds per point, threshold chosen on validation, scored once on
the frozen test split). Method: disposable script against a 297-target snapshot
of cache v1; no split, config or registry row was touched.

| Train rows | Champion F1 (min-max) | Champion AUC | Vetting F1 | Vetting AUC |
|---|---|---|---|---|
| 20 (10%) | 0.658 (0.533-0.774) | 0.770 | 0.769 | 0.831 |
| 52 (25%) | 0.856 (0.786-0.903) | 0.933 | 0.862 | 0.933 |
| 104 (50%) | 0.922 (0.903-0.933) | 0.967 | **0.933** | 0.967 |
| 156 (75%) | 0.906 (0.889-0.933) | 0.970 | 0.929 | 0.979 |
| 208 (100%) | 0.933 (0.933) | 0.984 | 0.933 | 0.996 |

Two conclusions, both awkward and both useful:

1. **The champion is not data-starved on these features.** F1 is flat from ~104
training rows; doubling to 208 bought +0.011, which is inside the interval. More
light curves of the same kind will mostly narrow the confidence interval, not
lift F1. That is exactly what the v2 re-score is now expected to show, and it is
pre-registered above.
2. **The test split, not the model, is the limiting factor.** Both feature sets
hit the same 14-TP / 2-FP ceiling at 104 rows. The two remaining errors are the
shallow low-SNR signals diagnosed above; separating those needs centroid motion
or difference imaging, a new data modality rather than more of the same photons.

Threshold robustness on the validation split (full training set): every threshold
in **0.94-0.97** is within 0.005 of the best validation F1 for the champion, and
0.97-0.98 for the challenger. The 0.94 used in the live champion sits inside that
plateau, so it is not a lucky spike - but the two false positives (p=0.995,
p=0.951) also sit inside it, which is why the F1 gap cannot be closed by moving
the threshold honestly.

### Pre-registration for the v2 re-score

A larger cache is downloading (900 targets). Before any v2 number exists, the
rules for reading it are fixed here:

1. The same four configs plus ONE pre-declared fifth challenger, same seeds, same
   threshold rule (validation F1). Only `data.split_version` changes, from `v1`
   to `v2`; the cache is never rebuilt with different labels. The fifth config,
   `runs/challenger_calibrated_live.json` (H-003), was written before split v2
   existed and never scored on v1 test data: one change, a strictly monotone
   Platt calibration fitted on the validation split, so the decision threshold
   is chosen on calibrated probabilities. Rationale: the cross-validation run
   above showed most of the F1 loss comes from transferring a threshold fitted
   on ~45 rows. Platt is used rather than isotonic because isotonic ties can
   lower ROC-AUC and trip the gate's no-degradation check. If it does not beat
   the champion on v2 F1, it is a REJECT row like any other.
2. Same gate: F1 strictly greater than the champion, AUC not degraded, run
   replayable. No margin tuning after seeing the result.
3. One pre-declared success criterion: a challenger KEEP row on real data. A
   second is champion F1 whose 95% interval is narrower than the v1 interval
   (0.815-1.000) - more data should buy precision even if nothing is promoted.
4. Forbidden: moving the decision threshold after seeing test, choosing the best
   of several seeds, or comparing against a champion retrained on test-inclusive
   data. Any of those turns the demo into a rehearsal.
5. If no challenger keeps, the v2 champion stands and the REJECT rows ship with
their diagnoses. A gate that only ever says yes is not a gate.

### v2 re-score: what the larger cache actually bought (results, not hopes)

The 900-target cache finished at **893 targets** (7 skipped: unreadable MAST data
products, each recorded with its reason in `data/live/cache_build.json`), which
froze a **new** split, `v2`, at `data/live/splits/v2.json`: train 625 / val 134 /
test 134, 98 primary test rows with 31 positives. Split v1 and every v1 artifact
are untouched - v2 is additive, created only because the cache grew, and H-003
was pre-registered to be scored on v2 only, never on v1 rows.

Dataset fingerprint `aa1bb5ca19a2390cc2f6cf1a6014d100f9b15dfe`,
split fingerprint `7449f8b87a9319d83537246ed1bfbf07a1e2e13b`, same seed, same
harness, same threshold rule for all five.

| Run | Config | F1 (95% CI) | AUC (95% CI) | Prec | Rec | Verdict |
|---|---|---|---|---|---|---|
| champion | `baseline_live_v2` | **0.9032** (0.8148-0.9706) | 0.9740 (0.9432-0.9949) | 0.903 | 0.903 | champion |
| challenger | `challenger_class_weight_live_v2` | 0.8667 (0.7619-0.9492) | 0.9740 (0.9431-0.9944) | 0.897 | 0.839 | REJECT: F1 -0.0365 |
| challenger | `challenger_calibrated_live_v2` (**H-003, pre-registered**) | 0.8667 (0.7619-0.9492) | 0.9740 (0.9432-0.9949) | 0.897 | 0.839 | REJECT: F1 -0.0365 |
| challenger | `challenger_vetting_features_live_v2` | 0.8485 (0.7419-0.9303) | 0.9692 (0.9352-0.9930) | 0.800 | 0.903 | REJECT: F1 -0.0547 |
| challenger | `cnn_live_v2` | 0.5918 (0.4772-0.6981) | 0.7029 (0.6045-0.8056) | 0.433 | 0.935 | REJECT: F1 -0.3114 |

Candidate-inclusive (all 134 test rows, CANDIDATE counted positive) for the
champion: F1 0.7273 / AUC 0.8917 - reported separately, never as the headline.

**Both pre-declared success criteria, scored honestly:**

1. *A challenger KEEP row on real data* - **not met.** Zero of four kept. The gate
   said no four times, on a split whose champion scores 0.90 rather than 0.93, so
   this is not an artefact of an easy draw.
2. *Champion F1 interval narrower than v1's 0.815-1.000* - **met.** Width 0.156
   versus 0.185, with 98 primary rows instead of 32. More data bought precision,
   exactly as predicted, and bought no F1.

**H-003 failed, and that is the useful result.** The pre-registered fix targeted
what CV said was the dominant loss: a threshold fitted on ~45 validation rows and
transferred to unseen hosts. Platt calibration was fitted on the v2 validation
split (slope 0.380, intercept -0.225, 61/134 positives) and the threshold was then
chosen on calibrated probabilities. It did not help: threshold moved 0.5 -> 0.78
and landed on the same confusion matrix as the uncalibrated balanced-weight model
(64 TN, 3 FP, 5 FN, 26 TP). The calibration removed threshold *scale* ambiguity,
not the errors. F1 loss was not a threshold-transfer problem, so the hypothesis -
written down before any v2 number existed - is falsified rather than refitted.

Read the champion number correctly: 0.9032 on 98 rows is **not** an upgrade of the
0.80 cross-validated estimate, and the two must never be swapped in a slide. The
98-row split is still a single draw; 0.80 on unseen host stars over all targets
remains the generalization claim. What the v2 run adds is a champion on 3x the
rows with a 16% tighter interval, and four rejection diagnoses instead of three.

### Uncertainty (do not quote a bare F1)

`python -m ml_sandbox.stability --predictions artifacts/<run>/predictions.csv`
resamples whole host stars (the split unit) 2,000 times and reports a 95%
percentile interval, then a JSON line. On the live champion:

| Metric | Point | 95% CI |
|---|---|---|
| F1 | 0.9333 | 0.8148 - 1.0000 |
| ROC-AUC | 0.9841 | 0.9412 - 1.0000 |

n=32 primary rows, 14 positives, 32 host groups. The interval is wide because the
test split is small; that is the honest precision of the demo claim. Quote the
interval in the UI and the pitch, and treat any challenger margin smaller than
the interval width as unresolved rather than as a win.

The champion's two false positives are **K03492.01** (p=0.9954) and
**K04641.01** (p=0.9505); every other test false positive scores below 0.14.
Both sit just above the val-selected threshold of 0.94 (the vetting challenger at
its 0.80 threshold flags the same two). With 14 positives, the champion already
sits at the split's practical ceiling: any challenger must remove one of those
two near-threshold false positives without losing recall.

Their catalog rows explain why they are hard and why a shape feature does not
rescue them: both are shallow, low-SNR signals (depths 101 and 116 ppm, model
SNR 13.6 and 9.0, radii 1.5 and 1.26 R-earth, impact parameters 0.71 and 0.03)
whose transit depths match the catalog radius ratio, i.e. consistent shallow
transits with a blend-like dilution rather than deep eclipsing binaries. The
discriminating evidence for that regime is centroid motion and imaging, which
this pipeline does not ingest. Candidate fold-shape features were tested on the
cached folds and did not separate the classes (best single-feature AUC 0.63, and
inverted at 0.44), so they were **not** added - recorded here so nobody
re-invents them at 2 a.m.

**Do not chase that.** Raising the threshold to 0.96 yields a perfect 1.0 on this
32-row test set and would be pure test-set fitting; it is not a model change and
must never be promoted. The honest read is that vetting features improved ranking
quality (AUC +0.012, and the candidate-inclusive F1 +0.025) but not enough to beat
a 14-positive F1 within the gate's margin. That is a REJECT row with a real
diagnosis, which is exactly what the registry is for.

Reproducibility: a clean-tree replay of `baseline_live` (config hash
`f542d54c219bb85f7c3ee68d43f7f827dfc58d8f`) produced identical metrics, dataset
fingerprint and split fingerprint. Wall time 0.6 s to train, 4.7 s for the CNN;
downloads, not compute, are the budget. `artifacts/replay_baseline_live/` holds
that replay: it is **not** a candidate and must not get its own registry row.

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

# live demo (requires requirements-astro.txt and a warm data/live cache)
python -m ml_sandbox.train --config ../runs/baseline_live.json --out ../artifacts/baseline_live
python -m ml_sandbox.train --config ../runs/challenger_vetting_features_live.json --out ../artifacts/challenger_vetting_features_live
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

Tuning check (2026-10-25): a 12-config validation sweep on `vetting_v1` found
best validation F1 0.9355 (500 trees, depth 5, `max_features="sqrt"`). Its single
test score was F1 0.9290 / AUC 0.9812, below the shipped challenger's 0.9305 /
0.9833, so **no config was adopted**. With 225 validation rows and 224 test rows,
0.01 differences are noise; do not select on test.

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

## NVIDIA GPU path (optional, measured)

The CNN accepts `training.device: "cuda"`; the GBM is sklearn and stays CPU. The
frozen reference runs are CPU, and CPU is still the default so existing configs
keep their hashes and their bit-for-bit replay.

Measured on 2026-10-25 (RTX 4050 Laptop, 6 GB, torch 2.5.1+cu121, 1,500 stub
targets, 400 bins, 64k-parameter CNN, identical config and seed):

| Device | CNN training time | Test F1 | Test AUC |
|---|---|---|---|
| cpu | 11.97 s | 0.8256 | 0.8989 |
| cuda | 2.36 s | 0.8256 | 0.8783 |

5.1x faster training, same F1; AUC moves slightly because CUDA kernels are not
bit-reproducible (determinism is enabled with `warn_only` on GPU, and
`CUBLAS_WORKSPACE_CONFIG=:4096:8` is set before the first GPU op). A GPU run is a
distinct config hash, so it never overwrites a CPU reference result.

```bash
# conda env with a CUDA torch build (this project's tf_gpu env has torch 2.5.1+cu121)
python -m ml_sandbox.train --config ../runs/cnn_live.json --out ../artifacts/cnn_live_cuda
# add "device": "cuda" under training in the config first
```

Why it is not the default: at 208-630 training rows a CNN epoch is seconds, and
the pipeline is dominated by MAST downloads, not compute. GPU capacity only starts
to matter for a wide CNN on raw cadence data - which is a post-hackathon direction,
not something to claim as a speedup we depend on.

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

1. **Live cache is 297 targets, not 1,500.** 300 requested, 3 skipped (recorded
   in `manifest.json.skipped`), 2,376 s at 3 workers. A 1,500-target cache is
   ~6-7 h of downloads. Growing past 297 requires bumping `data.split_version`
   to `v2` and re-running every champion and challenger - the frozen split
   refuses new targets by design.
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
   TAP query.10. **`git_dirty` disables replayability.** Commit first, then run the demo
    artifacts. `git status` includes untracked source files on purpose.
11. **One cache builder at a time.** There is no file lock; two concurrent builds
    in the same data root can interleave manifest writes.
12. **CI workflow is not active yet.** `ci.yml` at the repo root is B's to install
    at `.github/workflows/ci.yml` once `backend/app/` and `frontend/` exist. The ML
    test suite is ready for that workflow's `test` job.
13. **32 primary live test rows is small.** One flipped target moves F1 by ~0.03.
    Quote the confusion matrix and n with every score, never a bare F1.
14. **Two live false positives sit just above threshold.** That is the whole gap
    to the vetting challenger. Do not fix it by moving the threshold after seeing
    test; that is test-set fitting and the gate would rightly reject the run as
    not a real improvement. Both are shallow (100-116 ppm), low-SNR (9-14) signals
    that need centroid motion, which the cache does not carry.
15. **Fold-shape one-liners are a dead end.** Width-at-fraction-of-depth and
    ingress asymmetry features scored AUC 0.44-0.63 on the live folds; they would
    have added noise. Do not ship them without a real transit model fit.
16. **The residual error is pixel-level, not photometric.** 12 of our 25
    out-of-fold false positives carry the archive centroid-offset flag. Do not try
    to model blends away from folded flux; ingest Target Pixel Files or accept the
    ceiling. Archive vetting flags are label inputs - never train on them.

## Definition of done for the ML handoff to B

- [x] `python -m ml_sandbox.train ...` prints one JSON line and exits non-zero on failure
- [x] `run_record.json` matches the registry row contract (verdict PENDING)
- [x] Same config + same dataset fingerprint -> identical metrics (tested)
- [x] Host-star leakage test and frozen-split refusal test
- [x] Baseline + CNN trained and scored by the same harness
- [x] Live cache built (297 targets) and all four configs re-scored on it
- [x] Same-config replay reproduces live metrics, dataset and split fingerprints
- [ ] B inserts `run_record.json` rows and applies `promote()`
- [ ] FREEZE replay on a second machine (same fingerprint, same metrics)
