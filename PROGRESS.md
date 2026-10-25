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
