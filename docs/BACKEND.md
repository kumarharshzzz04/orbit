# docs/BACKEND.md - FastAPI + Registry + CI (Owner: B)

The spine: REST + WebSocket + persistence + registry, and it spawns the ML sandbox
as a subprocess (crash isolation). Single FastAPI app, strict layout.

## Success criteria

- [x-CP1] App boots; SQLite schema created (6 tables); POST /api/missions works
- [x-CP1] WS `/ws/{mission_id}` broadcasts orchestrator output from the canned transcript
- [x-CP2] Registry API: experiments append-only; artifacts endpoint streams files
- [x-CP2] `promote()` gate unit-tested (KEEP and REJECT paths)
- [x-CP2] CI green: lint + test + smoke
- [ ] FREEZE: mock LLM smoke (`LLM_MODE=mock`) gives a verdict in < 30s

## Layout (the contract)

```
backend/
  app/
    main.py            # FastAPI factory, CORS, startup
    routers/           # runs.py experiments.py candidates.py data.py ws.py
    services/          # orchestrator.py llm.py registry.py graph.py
    db/                # models.py (SQLModel) session.py
    schemas/           # pydantic: AgentMessage, Proposal, Verdict, WSEvent
  ml_sandbox/          # owned by C - see docs/ML.md
  tests/               # schema tests, gate tests, replay test
```

## API surface

| Method | Path | Purpose |
|---|---|---|
| POST | /api/missions | start mission (question, budget_rounds) |
| GET | /api/missions/{id} | status: round, agents idle/busy |
| GET | /api/experiments | registry listing |
| GET | /api/experiments/{id}/artifacts | metrics JSON, confusion matrix, weights |
| POST | /api/data/cache | trigger KOI/light-curve caching (progress via WS) |
| GET | /api/graph | nodes+edges for graph panel |
| WS | /ws/{mission_id} | agent_message / run_progress / run_metrics / verdict / system |

## Data model (SQLite + SQLModel)

`missions` - `hypotheses` - `experiments` (append-only, the heart) - `papers` -
`graph_edges` - `messages` (full transcript). Field lists are in `AGENTS.md` 3.2.
Corrections to experiments = new row, never an UPDATE.

## Promotion gate (services/registry.py)

```python
def promote(champion, challenger, margin=0.0):
    if challenger is None or not challenger.replayable:
        return Verdict.REJECT, "run not replayable"
    better_f1 = challenger.f1 > champion.f1 + margin
    safe_auc  = challenger.roc_auc >= champion.roc_auc - 1e-9
    if better_f1 and safe_auc:
        return Verdict.KEEP, "beats champion on F1, AUC not degraded"
    return Verdict.REJECT, diagnose(champion, challenger)
```

Rules: unit-tested with synthetic pairs; margin default 0.0 for the demo; `diagnose()`
returns a one-line plain-language cause (goes to the REJECTED card).

## CI (.github/workflows/ci.yml)

Stages: `lint` (ruff, black --check) -> `test` (pytest: schemas, gate, replay) ->
`smoke` (uvicorn boots with `LLM_MODE=mock`, mock mission returns a verdict < 30s)
-> `progress-guard` (fails if PROGRESS.md has no entry in the last 6h during the
hackathon window). GitHub Actions free-tier runners - the pipeline never
depends on paid features.

## Gotchas

- SQLite + multiple uvicorn workers = lock city. Run ONE worker (`uvicorn ... --workers 1`).
- Long ML runs must never run in the request thread - `BackgroundTasks` + subprocess.
- WS broadcast helper must catch dead connections (demo Wi-Fi will drop at least once).
