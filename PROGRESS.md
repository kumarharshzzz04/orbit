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

## 2026-10-25 14:34 - Member C (ML)
DONE: repo scaffold pushed to github.com/kumarharshzzz04/orbit (private); full ML sandbox
      built: KOI TAP labels (9,564 usable) + live MAST path, 12 real targets cached
      (sequential 546s vs `--workers 3` 186s, identical fingerprint), deterministic
      preprocessing, content-hashed cache + packed fast path, host-grouped frozen split
      v1 (1,051/225/224), GBM + CNN under one harness, 58 tests green.
      Stub metrics: baseline F1 0.837/AUC 0.899; CNN F1 0.821/AUC 0.879;
      vetting-features challenger F1 0.930/AUC 0.983; class-weight 0.826;
      CNN augmented 0.830. Dataset fingerprint ee1f7e04226f8e7b0ca68b3bd4dd8527877bac17,
      split fingerprint 303b6081ebb5002449fae5de31b30f5adb78a732.
NEXT:  full live 1,500-target cache; B wires registry/promote(); A consumes run_record.json
BLOCKED: none
NOTE:  stub data is synthetic - never quote these as Kepler performance. Full live cache is
      bandwidth-bound (~20s/target effective at 3 workers; 1,500 targets ~6-7h). Do NOT use
      threads for MAST: astroquery closes shared stdout; downloads are process-isolated.
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
