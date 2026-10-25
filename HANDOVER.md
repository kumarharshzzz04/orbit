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
   - FastAPI app factory in `backend/app/main.py` (skeleton)
   - SQLite schema: 8 tables (missions, hypotheses, experiments, experiment_decisions, experiment_attempts, papers, graph_edges, messages)
   - Registry service: `insert_experiment()`, `promote()`, `bootstrap_champion()`, `_evaluate_gate()`
   - Gate logic: F1 improvement + AUC safety margin; replayability gate; null champion floor (F1>0, AUC>=0.5)
   - `bootstrap_champion()` durably commits REJECT decisions before raising (fresh-session verified)
   - 43 database tests covering: schema creation, FK enforcement, unique constraints, attempt lifecycle, registry promotion, bootstrap, concurrency (BEGIN IMMEDIATE serialization), transaction rollback
   - All 73 ML sandbox tests still pass
   - Total: 116 tests passing

   ML frozen on real data:
   - 297 live Kepler targets cached (300 requested, 3 skipped)
   - Live split v1 (208/45/44, primary test 32 with 14 positives): champion F1 0.9333/AUC 0.9841
   - Vetting challenger F1 0.9333/AUC 0.9960 -> REJECT; class-weight 0.9286 and CNN 0.7368 -> REJECT
   - Clean-tree replay reproduced every metric
   - 1,500-target stub cache; dataset fingerprint `ee1f7e04226f8e7b0ca68b3bd4dd8527877bac17`
   - Baseline F1 0.8372/AUC 0.8988; vetting challenger F1 0.9305/AUC 0.9833
   - 900-target live cache downloading (66%, 597/900)

2. WHAT IS BROKEN:
   - `agent_orchestrator` loop (A), `frontend/` Vite UI (D), CI workflow (B)
   - FastAPI routers not yet wired to registry (endpoints stubbed)
   - WebSocket endpoint `/ws/{mission_id}` not implemented
   - `ci.yml` still at repo root (needs move to .github/workflows/)
   - Live gate has no KEEP: the champion already sits at the 14-positive ceiling, so every live challenger ties or loses
   - ML records stay `verdict: PENDING` until routers wired

3. NEXT ACTIONS:
   (1) B: wire FastAPI routers to registry; implement WS broadcast; move CI to .github/workflows/
   (2) A: build orchestrator loop + agent prompts + NIM/Nemotron LLM connector (NVIDIA event)
   (3) D: build Vite UI against `docs/fixtures/ws_events.jsonl`, then switch to B's socket
   (4) C: download 300-target live cache (~75-90 min at `--workers 3`), score baseline and vetting challenger; hand B the four live `run_record.json` rows

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