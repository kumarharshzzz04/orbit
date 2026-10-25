# AGENTS.md - ORBIT Coordination Protocol

**Read this file first. Update it every pull request. It exists for humans AND AI agents.**

Any contributor (teammate or AI coding session) must be able to become productive from this
repository alone in under 5 minutes. That only works if this file stays true. Stale
information here is worse than no information.

---

## 1. Current State (update on EVERY pull request - one writer: Member A)

```
LAST UPDATED:   2026-10-25 15:02  (by C; owner A to confirm)
SYSTEM STATE:   [ ] not started   [x] scaffolding   [ ] walking skeleton (CP-1)
                [ ] feature complete (CP-2)         [ ] frozen (h27)
WORKING:        ML sandbox complete: 1,500-target stub cache; 59 tests; baseline
                F1 0.837/AUC 0.899; CNN F1 0.821; vetting challenger F1 0.930/AUC 0.983;
                12-target live MAST smoke; shared fixtures under docs/fixtures/
BROKEN:         backend app/registry, agent loop, frontend, active CI (not built yet)
NEXT UP:        B: FastAPI + registry + promote(); A: orchestrator loop;
                D: Vite UI against docs/fixtures/ws_events.jsonl; C: 300-target live cache
DEMO RISK:      full live cache not downloaded; real-data scores unmeasured;
                ci.yml is still at repo root; only vetting challenger clears the gate
```

## 2. Owners (one owner per module, at any moment)

| Module | Owner | Doc |
|---|---|---|
| Agent orchestrator + prompts + event schema | **A** (integration lead) | `docs/AGENTS_SYSTEM.md` |
| FastAPI app, SQLite, registry, CI | **B** | `docs/BACKEND.md` |
| Data, preprocessing, models, eval harness | **C** | `docs/ML.md` |
| React mission control | **D** | `docs/FRONTEND.md` |

With 3 members: B absorbs CI + data download; C hands eval harness to B at CP-1;
graph panel becomes optional. Owner changes must be recorded here AND in `HANDOVER.md`.

## 3. Contracts everyone codes against (changing these needs A's sign-off)

### 3.1 WebSocket event schema (backend -> frontend)

```json
{ "event": "agent_message | run_progress | run_metrics | verdict | system",
  "mission_id": "string",
  "payload": { ... } }
```

- `agent_message.payload`: `{ "agent": "researcher|hypothesizer|skeptic|experimenter|evaluator|orchestrator",
  "round": int, "type": "evidence_card|proposal|critique|run_record|verdict|status", "body": string, "refs": [] }`
- Other payloads (master plan table 8; A owns final sign-off):
  - `run_progress.payload`: `{ "run_id": string, "stage": string, "percent": float }`
  - `run_metrics.payload`: `{ "run_id": string, "metrics": { "accuracy": float, "precision": float, "recall": float, "f1": float, "roc_auc": float } }`
  - `verdict.payload`: `{ "run_id": string, "kept": bool, "rationale": string }`
  - `system.payload`: `{ "level": "info|warn|error", "text": string }`
- Frontend renders any unknown `type` as plain text. Backend never breaks the enum silently.
- Replayable sample stream: `docs/fixtures/ws_events.jsonl`.

### 3.2 Experiment registry row (append-only)

```json
{ "id": "...", "hypothesis_id": "...", "config_hash": "sha1", "seed": 42,
  "git_commit": "sha", "dataset_fingerprint": "sha1",
  "metrics": { "accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "roc_auc": 0.0 },
  "artifact_path": "artifacts/<run_id>/", "verdict": "KEEP | REJECT | PENDING",
  "diagnosis": "string | null", "created_at": "iso8601" }
```

- Rows are NEVER edited or deleted. Corrections = new row referencing the old id.
- Champion = the highest-gated KEEP row. `promote()` in `services/registry.py` is the
  single decision point; it is unit-tested and nobody argues with it at 2 a.m.

### 3.3 ML sandbox CLI (stdin/stdout contract)

```bash
python -m ml_sandbox.train --config run.json --out artifacts/<run_id>/
# stdout (last line, JSON): { "ok": true, "metrics": {...}, "artifact": "..." }
```

A crash exits non-zero and the API survives. LLM and MAST both have mock modes
(`LLM_MODE=mock`, `DATA_MODE=stub`) - exercised daily, they are features, not shame.

## 4. Conventions

- **Branches:** `main` is demo-safe. Work in `feat/<module>-<thing>`. PR into `main`, even for solo work.
- **Commits:** conventional commits (`feat:`, `fix:`, `docs:`, `chore:`). One logical change per commit.
- **Format:** ruff + black on Python, eslint on TS - CI enforces, no debates.
- **Secrets:** real keys live in `.env` (git-ignored). `.env.example` carries placeholders only.
- **No AI attribution:** never add an AI tool as commit co-author, contributor or repository collaborator. Commits use the human teammate's identity only.
- **PR checklist:** schema unchanged? (if changed: A approved) / tests pass / PROGRESS.md block added / AGENTS.md section 1 updated.

## 5. NEVER do (break these and the demo/science breaks)

1. **Never regenerate the frozen test split.** Created once (Day 1, `data/splits/`), fingerprinted. The gate is only as credible as the split is stable.
2. **Never edit or delete registry rows** (append-only, see 3.2).
3. **Never commit real API keys** or the `data/` folder.
4. **Never change the WS event schema** without Member A's sign-off + frontend update in the same PR.
5. **Never bump dependencies after hour 20** of the sprint.
6. **Never train the challenger on data that includes the test split** - the Skeptic exists because of this exact mistake.

## 6. Integration checkpoints (hard gates)

| CP | When | Exit criterion | Called by |
|---|---|---|---|
| CP-1 | Day 1, h10 | Mission in -> 1 agent reply -> panel shows it; baseline trains | all |
| CP-2 | Day 2, h20 | Full gated loop (propose -> veto -> train -> verdict) in registry | all |
| FREEZE | Day 3, h27 | Demo-script-only fixes; backup video recorded | A |

## 7. AI-agent sessions (Claude/Copilot/etc.)

- Start from this file + the module doc for your task + the last 3 `PROGRESS.md` blocks.
- Work inside ONE module; do not refactor across modules.
- Before ending, write: code PR + `PROGRESS.md` block + updated section 1 (or tell the
  human to). An AI session that forgets the log counts as a crashed session.
- If blocked > 20 minutes: stop, write the blocker with a reproducing command, move on.
