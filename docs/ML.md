# docs/ML.md - Exoplanet Intelligence Pipeline (Owner: C)

Two honest model families so the agent debate has something real to improve:
a classical baseline (GBM) and a 1D CNN, both scored by ONE evaluation harness on
ONE frozen split. Precedent: NASA ExoMiner validated 301+ exoplanets with deep
learning on Kepler photometry - we aim for a credible demo model, not SOTA.

## Success criteria

- [x-CP1] KOI labels + >= 200 light curves cached; fold+bin vectors built
- [x-CP1] Baseline trains and reports F1 on the frozen split
- [x-CP2] CNN v1 trained; both models scored by the same harness; gate wired
- [x-CP2] Challenger-vs-champion promotion demonstrated (real or seeded)
- [ ] FREEZE: full cache re-run reproduces metrics (fixed seeds, fingerprinted data)

## Data plan

| Item | Decision |
|---|---|
| Labels | NASA Exoplanet Archive KOI cumulative: CONFIRMED + CANDIDATE vs FALSE POSITIVE |
| Signals | MAST Kepler long-cadence PDCSAP (lightkurve). TESS only where fast |
| Volume | 1,500-2,000 targets, cached Day 1 (download-bound) |
| Split | Grouped by HOST STAR, 70/15/15, frozen to `data/splits/v1` + fingerprint |
| Unit | 400-bin folded flux vector + 12 engineered features |

Primary metric treats CONFIRMED vs FALSE POSITIVE as truth (CANDIDATE labels are
uncertain); report candidate-inclusive numbers separately in the model card.

## Preprocessing (pure functions, cached, boring on purpose)

`lightkurve.download PDCSAP` -> drop NaNs -> sigma-clip -> detrend (Savitzky-Golay)
-> normalize -> fold at KOI period/t0 -> bin to 400 points -> `.npz` +
feature vector (depth, duration, SNR, period, radius_ratio, n_companions, ...).
Byte-identical inputs for challenger and champion is the whole credibility story.

## Models

| Model | Family | Input | Notes |
|---|---|---|---|
| orbit-baseline-v1 | GradientBoosting (sklearn) | 12 features | 300 trees, depth 6; trains in seconds; expect F1 ~0.85-0.90 |
| orbit-cnn-v1 | 1D CNN (PyTorch, CPU) | 400-bin flux | Conv1D(32)-MaxPool-Conv1D(64)-MaxPool-Conv1D(96)-GlobalPool-Dropout(.3)-FC(64)-sigmoid; ~90k params; few min/train |

First agent missions target interpretable wins: class weighting, feature adds,
period-error augmentation - NOT architecture golf.

## Metrics & the gate

accuracy, precision, recall, F1, ROC-AUC + confusion-matrix artifact on the same
frozen test split. Promotion: challenger F1 > champion F1 AND ROC-AUC not degraded,
run replayable (config hash + seed + commit + dataset fingerprint all present).
Failures are REJECT rows with the Evaluator's diagnosis - negative results are assets.

## Gotchas

- LEAKAGE: split by host star, never by row. The Skeptic's #1 attack vector; there is a test.
- Class imbalance: keep `class_weight`/pos_weight in the config JSON, not hardcoded.
- CPU training: subsample flux vectors to 400 bins, early stopping on val F1; if a run
  exceeds ~10 min, shrink, do not wait.
- Every run records seed=42 default; changing seeds is allowed but must be in the config.
