# HANDOVER.md - Module Handover Records

Fill one block **before leaving the keyboard** whenever a module changes hands -
even mid-day, even for one hour. Four questions, no essays. Newest at top.

---

## 2026-10-25 19:45 - B2 Backend (Registry + Persistence) : B -> A/D (ready to integrate)

1. WHAT WORKS:

   ```bash
   cd backend
   python -m pytest tests/ -q  # 116 tests pass in ~80s (43 registry + 73 ML)
   python -m ml_sandbox.train --config ../runs/baseline_v1.json --out ../artifacts/baseline_v1
   python -m pytest tests/test_b2_database.py -v  # 43 registry/schema tests pass
   ```

   Backend complete:
   - SQLite schema: 8 tables (missions, hypotheses, experiments, experiment_decisions, experiment_attempts, papers, graph_edges, messages)
   - Registry service: `insert_experiment()`, `promote()`, `bootstrap_champion()`, `_evaluate_gate()`
   - Gate logic: F1 improvement + AUC safety margin; replayability gate; null champion floor (F1>0, AUC>=0.5)
   - `bootstrap_champion()` durably commits REJECT decisions before raising (fresh-session verified)
   - 43 database tests covering: schema creation, FK enforcement, unique constraints, attempt lifecycle, registry promotion, bootstrap, concurrency (BEGIN IMMEDIATE serialization), transaction rollback
   - Full suite: 118 passed, 1 skipped (`tests/test_cnn.py`, torch absent in that venv)

   ML frozen on real data, split v2:
   - 893 live Kepler targets cached (900 requested, 7 unreadable MAST products skipped, reasons in `cache_build.json`)
   - Split v2 frozen at 625/134/134; dataset `aa1bb5ca19a2390cc2f6cf1a6014d100f9b15dfe`, split `7449f8b87a9319d83537246ed1bfbf07a1e2e13b`
   - Champion F1 0.9032 (0.8148-0.9706) / AUC 0.9740 on 98 primary test rows
   - All five challengers REJECT: class-weight 0.8667, pre-registered H-003 Platt calibration 0.8667, H-004 HistGBM 0.8571, vetting features 0.8485, CNN 0.5918
   - H-004 came from a committed 41-config search over 4 model families on train+val only, and still lost on the frozen draw
   - Registry seeding handoff: `python backend/scripts/seed_registry.py --db data/orbit.db` bootstraps the champion and gates every challenger
   - H-003 was written before split v2 existed; it is falsified, not refitted
   - Generalization estimate remains F1 0.80 +/- 0.04 / AUC 0.934 from host-grouped 5-fold CV over the 297-target v1 snapshot (NOT yet re-run on 893)
   - Split v1 and its artifacts are untouched; v2 was additive, created only because the cache grew
   - 1,500-target stub cache; dataset fingerprint `ee1f7e04226f8e7b0ca68b3bd4dd8527877bac17`; stub baseline F1 0.8372/AUC 0.8988

2. WHAT IS BROKEN:
   - `agent_orchestrator` loop (A), `frontend/` Vite UI (D), CI workflow (B)
   - No FastAPI app object and no routers exist at all - only `app/db/` and `app/services/registry.py`
   - WebSocket endpoint `/ws/{mission_id}` not implemented
   - `ci.yml` still at repo root (needs move to .github/workflows/)
   - Live gate has no KEEP: the champion already sits at the 14-positive ceiling, so every live challenger ties or loses
   - ML records stay `verdict: PENDING` until routers wired

3. NEXT ACTIONS:
   (1) B: wire FastAPI routers to registry; implement WS broadcast; move CI to .github/workflows/
   (2) A: build orchestrator loop + agent prompts + NIM/Nemotron LLM connector (NVIDIA event)
   (3) D: build Vite UI against `docs/fixtures/ws_events.jsonl`, then switch to B's socket
   (4) C: done - hand B the five v2 `run_record.json` rows in `artifacts/*_v2/` for registry seeding; optionally re-run host-grouped CV on 893 to replace the 297-target 0.80 estimate

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
3. NEXT ACTIONS:    (concrete, owner, artifact)
4. WATCH OUT:       (immutable invariants, gotchas, do-not-do)
```

---