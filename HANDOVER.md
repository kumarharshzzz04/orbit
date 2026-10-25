# HANDOVER.md - Module Handover Records

Fill one block **before leaving the keyboard** whenever a module changes hands -
even mid-day, even for one hour. Four questions, no essays. Newest at top.

---

## 2026-10-25 15:02 - ML sandbox : C -> A/B/D (ready to integrate)

1. WHAT WORKS:

   ```bash
   cd backend
   python -m ml_sandbox.build_cache --mode stub --targets 1500
   python -m ml_sandbox.train --config ../runs/baseline_v1.json --out ../artifacts/baseline_v1
   python -m ml_sandbox.train --config ../runs/challenger_vetting_features.json --out ../artifacts/challenger_vetting_features
   python -m pytest -q
   ```

   Expected: 1,500 targets in ~12 s, dataset fingerprint
   `ee1f7e04226f8e7b0ca68b3bd4dd8527877bac17`; baseline F1 0.8372/AUC 0.8988;
   vetting challenger F1 0.9305/AUC 0.9833; 59 tests passed.
   Live MAST path: 12 real targets cached; same fingerprint with 1 or 3 workers.
   Full 1,500-target live cache not downloaded.

2. WHAT IS BROKEN:  `backend/app/`, `frontend/` and the orchestrator do not exist yet.
                    `promote()` is not wired; ML records stay `verdict: PENDING`.
                    No real-data test metrics yet: stub only, and 12 live targets
                    are too few for three non-empty splits.
                    CI is inactive; `ci.yml` is still at repo root.

3. NEXT ACTIONS:    (1) B: build FastAPI + registry + `promote()`, ingest
                    `artifacts/<run>/run_record.json`; use
                    `docs/fixtures/registry_rows.example.json` as the target shape.
                    (2) A: build the loop; Experimenter runs the exact CLI and
                    applies exactly one config change; use
                    `docs/fixtures/proposal.example.json`.
                    (3) D: build the Vite UI against
                    `docs/fixtures/ws_events.jsonl`, then switch to B's socket.
                    (4) C: download a 300-target live cache (~75-90 min at
                    `--workers 3`), score baseline and vetting challenger once.

4. WATCH OUT:       Frozen split v1 is immutable. Never rebuild the cache with a
                    different target set under the same split version; bump
                    `data.split_version` deliberately. Stub metrics are pipeline
                    proof, not Kepler performance. `replayable` is true only on a
                    clean git tree. `data/` and `artifacts/` are git-ignored, so
                    rebuild locally. Live downloads use processes, never threads.
                    Never add an AI co-author or repository collaborator.

START HERE:         A: `docs/AGENTS_SYSTEM.md` + `docs/fixtures/proposal.example.json`
                    B: `docs/BACKEND.md` + `docs/fixtures/registry_rows.example.json`
                    D: `docs/FRONTEND.md` + `docs/fixtures/ws_events.jsonl`
                    All: `README.md`, `AGENTS.md`, `docs/ML.md`

PR: none (direct main)   Commit: this handoff (ML code verified at d9ca7a6)   Uncommitted: no

---

## Template (copy, fill, keep to <15 lines)

```
### YYYY-MM-DD HH:MM - <module> : <from> -> <to>
1. WHAT WORKS:      (runnable proof: command + expected result)
2. WHAT IS BROKEN:  (symptom + how to reproduce)
3. NEXT ACTIONS:    (ordered, concrete, 1-3 items)
4. WATCH OUT:       (traps, TODOs, fragile parts)
PR: <link>   Uncommitted: <yes/no - what/where>
```

---

## Example

```
### 2026-11-09 02:10 - ML pipeline : C -> B (overnight coverage)
1. WHAT WORKS:      python -m ml_sandbox.train --config runs/cnn_v1.json --out /tmp/a1
                    -> ok:true, f1 0.905, artifacts written; gate test passes
2. WHAT IS BROKEN:  wotan detrender segfaults on 3 KOIs (e.g. KIC 8462852) -
                    skipped via blacklist in ml_sandbox/preprocess.py:87
3. NEXT ACTIONS:    (1) wire eval harness to registry API (B), (2) re-run CNN v2
                    with class weights, (3) add confusion-matrix artifact
4. WATCH OUT:       DO NOT regenerate splits/ - frozen v1; seeds fixed at 42;
                    wotan imported lazily (slow first call is normal)
PR: github.com/your-team/orbit/pull/14   Uncommitted: no
```
