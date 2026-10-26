# PROGRESS.md - ORBIT Work Log (append-only)

One block per work session. Newest at the TOP. Never edit old blocks - append a
correction as a new block. During the hackathon window, CI fails if no block was
added in the previous 6 hours (see `.github/workflows/ci.yml` -> `progress-guard`).

Format:

```
## YYYY-MM-DD HH:MM - <Member> (<track>)
DONE:    concrete things that now work (with numbers where possible)
NEXT:    the next 1-3 actions, named precisely
BLOCKED: blockers + reproducing command (or "none")
NOTE:    decisions, surprises, gotchas the next person needs
```

---

## 2026-10-26 - Member C (ML: model search + handoff)
DONE: tried to beat the champion honestly, and failed in a useful way. New
      `ml_sandbox.model_search` runs a declared 40-config grid across GradientBoosting,
      HistGradientBoosting, RandomForest and ExtraTrees on the v2 train+val pool only
      (759 rows; the 134 frozen test rows are excluded in code). Champion 5-fold F1
      0.7994 +/- 0.0299 / AUC 0.9484 - which agrees with the 297-target estimate of
      0.801, so the generalization number is stable across caches. One candidate cleared
      the paired-interval rule: HistGBM +0.0215 [+0.0005, +0.0424]. Added it as model
      family `hist` (config validation, training dispatch, tests) and as H-004
      (`runs/challenger_hist_live.json`), trained once on the frozen split: F1 0.8571 /
      AUC 0.9716 -> REJECT. The thin CV lower bound did not transfer to a 98-row draw.
      Suite 118 passed + 1 skipped. Also wrote `backend/scripts/seed_registry.py`: it
      creates the seed mission + hypothesis rows the registry FK requires, bootstraps
      the champion, and gates all five challengers - verified on a temp DB, all REJECT.
NEXT:  B: main.py + routers; A: CP-1 seam; D: UI. C: ML track closed.
BLOCKED: none
NOTE: registry `insert_experiment()` fails with a FOREIGN KEY error when a run_record
      carries `hypothesis_id` but no Hypothesis row exists. Not a bug in the registry -
      the orchestrator is supposed to create mission + hypothesis first. The seed script
      now does that for the ML runs. Anyone inserting raw run_records hits it immediately.

---

## 2026-10-26 - Member C (ML + backend review)
DONE: closed the ML track on split v2. The 893-target live cache completed (900 requested,
      7 unreadable MAST products skipped with reasons), the v2 watcher froze split v2 at
      625/134/134 (dataset aa1bb5ca, split 7449f8b8) and scored five configs. Champion
      `baseline_live_v2` F1 0.9032 (0.8148-0.9706) / AUC 0.9740 on 98 primary test rows.
      All four challengers REJECT: class-weight 0.8667, pre-registered H-003 Platt
      calibration 0.8667, vetting features 0.8485, CNN 0.5918. Both pre-declared success
      criteria scored: promotion 0/1 (met: no), interval narrowing 1/1 (0.185 -> 0.156
      wide). Reviewed and ran B's B2 push: 43 registry tests pass, full suite 113 passed +
      1 skipped. Added the missing backend deps to requirements.txt (sqlmodel/SQLAlchemy/
      fastapi) - without them the documented `pip install -r requirements.txt && pytest`
      fails at collection. B's push is NOT lint-clean despite the claim: 79 ruff errors and
      6 files black would reformat, all in B's module; I reported it rather than reformat
      someone else's files, since CI is supposed to own that. Corrected AGENTS.md section 1: CP-1 un-ticked and the "FastAPI
      app" claim removed (there is no main.py, no router, no WS broadcast). Wrote
      backend/CHANGES_2026-10-26.txt and docs/AGENTS_CHANGES_2026-10-26.txt with the
      review findings. README and docs/ML.md updated to the v2 numbers.
NEXT:  B: main.py + routers -> registry, WS broadcast, move ci.yml to .github/workflows/.
      A: CP-1 first (one mission -> one agent reply -> one panel), then the six-agent loop.
      C: hand B the v2 run_record.json rows for registry seeding.
BLOCKED: none
NOTE: H-003 is the most useful artifact in the repo. It was written before split v2
      existed, could not see v1 test rows, and came back REJECT with a number. Do not
      describe it as a near miss - the calibration fixed threshold scale but changed no
      decisions (identical 64/3/5/26 confusion matrix to the balanced-weight model).
      Also: `promote()` returns Verdict.REJECT for operational errors (missing id, double
      promote) with no row written - fine for the registry, misleading for any UI that
      renders the returned verdict. See backend/CHANGES_2026-10-26.txt section 2b.

---

## 2026-10-25 18:05 - Member C (ML + docs)
DONE: made the scale claim reproducible instead of rhetorical. New `ml_sandbox.catalog_cv`
      trains the 12 catalog features on the whole KOI table (9,564 targets / 8,214 hosts)
      with host-grouped 5-fold CV and a per-fold inner-validation threshold, scored on
      primary truth: F1 0.883 +/- 0.017, AUC 0.971 +/- 0.005 (pooled OOF F1 0.883 over
      7,587 primary rows: 4,517 TN / 322 FP / 321 FN / 2,427 TP). Report committed at
      runs/evidence/catalog_full_cv.json with the KOI SHA-1 and run commit. README rewritten
      so each claim links to the artifact or command behind it, with an explicit limitations
      section and the NVIDIA/CUDA numbers. 73 tests green, ruff+black clean.
NEXT: 900-target cache at 597/900 (66%), ETA ~19:05; then the v2 and calibration watchers
      fire. Report the v2 verdicts against the pre-registered expectation.
BLOCKED: none
NOTE: the earlier inline 0.835/0.923 catalog figure scored candidate-inclusive rows at a
      single 0.5 threshold (reproduced 0.838/0.926); it is superseded. Catalog features are
      transit-fit parameters and partly correlated with the archive disposition, so 0.883
      is a scale/protocol check, not independent evidence. Never present it as beating the
      0.801 folded-pixel CV - different populations.

---

## 2026-10-25 17:45 - Member C (ML)
DONE: quantified the residual error with the archive's pixel-vetting columns (12 of 25
      out-of-fold false positives carry koi_fpflag_co; both frozen-split FPs are
      centroid-offset blends at 8.52" and 3.69"). Added an optional CUDA path for the CNN
      (11.97s -> 2.36s training, 5.1x, identical F1 0.8256, AUC differs because CUDA is
      not bit-reproducible) plus Python 3.10 compatibility for the tf_gpu env. Backend is
      ruff+black clean; 73 tests green.
NEXT: 900-target cache at 58% (530/900). On completion the v2 watcher re-scores four
      configs and the calibration watcher adds the pre-registered Platt challenger.
BLOCKED: none
NOTE: archive vetting flags are inputs to the official disposition - never use them as
      features, only to explain errors. GPU changes speed only: it does not move F1 or the
      ceiling, so do not let a deck imply otherwise. The CUDA env is Python 3.10, which is
      why the code uses datetime.timezone.utc and ruff ignores UP017.

---

## 2026-10-25 17:15 - Member C (ML)
DONE: two independent checks on the frozen 297-target live set, both done before v2 exists.
      (1) Host-grouped 5-fold CV (threshold fixed from the original validation split, so no
      fold self-selects): champion F1 0.801 +/- 0.036, AUC 0.934 +/- 0.030, pooled OOF
      0.800 over 234 primary rows / 89 positives (120 TN, 25 FP, 13 FN, 76 TP); vetting
      challenger 0.810 +/- 0.072, AUC 0.946 +/- 0.037. (2) Data-scaling curve on stratified
      training subsets: F1 is flat from ~104 rows (0.922) to 208 (0.933), so more light
      curves buy precision, not F1. Both written into docs/ML.md with method and caveats.
NEXT: finish the 900-target cache (369/900 at 17:05, ~2h), auto re-score on split v2, then
      update the frozen report with the v2 verdicts and intervals.
BLOCKED: none
NOTE: the 0.933 frozen-split F1 is an easy draw - the same model scores 0.80 out-of-fold on
      unseen hosts. Always quote both, or the CV pair alone. The 0.94 threshold is not
      cherry-picked (validation plateau 0.94-0.97), but both false positives sit inside that
      plateau, so moving it honestly cannot close the gap. Remaining errors are shallow
      low-SNR signals; separating them needs centroid motion, a new data modality, not more
      Kepler light curves.

---

## 2026-10-25 16:45 - Member C (ML)
DONE: real-data ML is frozen. 297 live Kepler targets cached (300 requested, 3 skipped,
      294 hosts (145 FP / 89 CONFIRMED / 63 CANDIDATE), 2,376 s at 3 workers; dataset fp 3826e7f3..., live split v1 fp
      d8aa6b99...; train 208 / val 45 / test 44, primary test 32 with 14 positives).
      All four configs retrained on it: champion F1 0.9333 / AUC 0.9841 / acc 0.9375
      (2 FP: K03492.01 p=0.995, K04641.01 p=0.951); vetting challenger F1 0.9333 /
      AUC 0.9960 -> REJECT (no F1 gain); class-weight F1 0.9286, CNN F1 0.7368 ->
      REJECT. Clean-tree replay of the champion reproduced every metric and both
      fingerprints. 59 tests green.
NEXT: B ingests the four live run_record.json rows and runs promote(); C hands over and
      supports the demo; only bump to split v2 + bigger cache if the team accepts a full
      re-score.
BLOCKED: none
NOTE: the live gate has no KEEP. That is a real result, not a bug: with 14 test positives
      the champion already sits at the ceiling, and the two false positives are just above
      the val threshold of 0.94. Raising the threshold to 0.96 would score 1.0 and is
      test-set fitting - do not do it, do not promote it. Stub mode still supplies a KEEP
      example for the demo (vetting challenger F1 0.930 vs 0.837). Every live number must
      be quoted with n and the confusion matrix.

---

## 2026-10-25 15:10 - Member C (ML)
DONE: handoff complete. Added shared fixtures (`docs/fixtures/ws_events.jsonl`,
      registry rows, one-change proposal), real handover block, per-role start
      sections in README/BACKEND/AGENTS_SYSTEM/FRONTEND, and WS payload shapes in
      AGENTS.md 3.1. Validation-only tuning sweep: best val F1 0.9355, test F1
      0.9290 < shipped 0.9305, so no new config adopted. 59 tests green.
NEXT: B registry + promote(); A orchestrator; D fixture-first UI; C 300-target live cache.
BLOCKED: none
NOTE: ML records stay PENDING until B's promote() runs. Stub metrics prove pipeline,
      not Kepler performance. Never tune on test; 225/224 val/test rows make 0.01 noise.

---

## 2026-10-25 14:34 - Member C (ML)
DONE: repo scaffold pushed to github.com/kumarharshzzz04/orbit (private); full ML sandbox
      built: KOI TAP labels (9,564 usable) + live MAST path, 12 real targets cached
      (sequential 546s vs `--workers 3` 186s, identical fingerprint; one download per
      host, warm rebuild 22s, same fingerprint), deterministic preprocessing,
      content-hashed cache + packed fast path, host-grouped frozen split
      v1 (1,051/225/224), GBM + CNN under one harness, 59 tests green.
      Stub metrics: baseline F1 0.837/AUC 0.899; CNN F1 0.821/AUC 0.879;
      vetting-features challenger F1 0.930/AUC 0.983; class-weight 0.826;
      CNN augmented 0.830. Dataset fingerprint ee1f7e04226f8e7b0ca68b3bd4dd8527877bac17,
      split fingerprint 303b6081ebb5002449fae5de31b30f5adb78a732.
NEXT:  full live 1,500-target cache; B wires registry/promote(); A consumes run_record.json
BLOCKED: none
NOTE:  stub data is synthetic - never quote these as Kepler performance. Full live cache is
      bandwidth-bound (~20s/target effective at 3 workers; 1,500 targets ~6-7h). Do NOT use
      threads for MAST: astroquery closes shared stdout; downloads are process-isolated and
      host-deduplicated (multiple KOI rows commonly share one kepid).
      The CNN losing is a real negative result, not a bug. Split v1 was
      re-frozen once before this commit after fixing the live raw-flux sigma clip; from this
      commit on it is frozen. The three example blocks below are the master-plan seed
      examples, not this repo's history.

---

<!-- ==================== copy the template below ==================== -->

## 2026-11-08 14:20 - Member C (ML)
DONE: cached 1,842 KOI light curves (Kepler only); fold+bin pipeline green; baseline GBM F1 0.87 on frozen split `data/splits/v1`
NEXT: CNN v1 training run (CPU, ~6 min); wire /api/experiments metrics
BLOCKED: none
NOTE: TESS downloads ~6x slower than Kepler - capped cache at Kepler, revisit post-hackathon

## 2026-11-08 11:05 - Member B (Backend)
DONE: FastAPI scaffold + SQLite schema (6 tables); POST /api/missions + WS /ws/{id} live; mission round-trips from curl
NEXT: registry API + artifact store
BLOCKED: need A's finalized WS payload enum (waiting since 10:30)
NOTE: SQLModel generated a warning on `graph_edges` - ignored, works

## 2026-11-08 09:30 - Member A (Agents)
DONE: 6 agent skeleton classes + system prompts v1; linear orchestrator replays canned transcript to WS
NEXT: wire Researcher tools (papers JSON + graph query); Skeptic veto path
BLOCKED: none
NOTE: kept prompts under 120 words each - long prompts drifted from JSON schema in smoke test
