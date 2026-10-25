# docs/FRONTEND.md - React Mission Control (Owner: D)

Single-screen "mission control". Dark space theme, one accent color per agent.
Everything the backend broadcasts appears within ~1s. Nothing on the demo screen
needs a page refresh.

## Success criteria (tick at CP-1 / CP-2 / FREEZE)

- [x-CP1] Vite scaffold + design tokens (dark theme, agent color map)
- [x-CP1] WebSocket client connects to `/ws/{mission_id}` and renders `agent_message`
- [x-CP1] Mission input posts to `POST /api/missions`
- [x-CP2] Light curve viewer (Plotly): folded flux + transit marker
- [x-CP2] Leaderboard: champion vs challenger rows, KEEP/REJECT chips, updates on `verdict`
- [x-CP2] Status rail: `run_progress` + `system` toasts, LLM provider badge
- [ ] FREEZE: reconnect replays transcript from `GET /api/missions/{id}`
- [ ] FREEZE: demo mission runs end-to-end on a cold browser cache

## Component tree

```
src/
  App.tsx                  # layout grid (debate | viewer/leaderboard | rail), theme
  api/useMissionSocket.ts  # ONLY WS writer -> Zustand store; reconnect + replay
  store/useOrbitStore.ts   # slices: messages[], runs[], champion, system[]
  panels/
    DebatePanel.tsx        # MessageBubble per agent; round badges; typing indicator
    LightCurve.tsx         # Plotly: flux line + shaded transit windows
    Leaderboard.tsx        # sortable metrics table + verdict history
    MissionInput.tsx       # question box + 3 one-click mission templates
    GraphPanel.tsx         # STRETCH: react-force-graph on GET /api/graph
  components/              # Avatar(colored initials, no emoji), MetricChip, RoundBanner
```

## State rules

- `useMissionSocket` is the ONLY writer to the store - all data flows WS -> dispatch -> slice.
- Unknown event types render as plain text (never crash on schema additions).
- Reconnect = refetch mission transcript, then live-tail (saves live demos).

## Demo-critical polish (budget: 3h, only after CP-2)

Agent avatars (colored initials), typing indicator while LLM streams, KEEP (green) /
REJECT (red) chips, "ROUND 2" banner when the Skeptic forces revision, subtle glow on
the champion row when it changes. Say no to everything else.

## Gotchas

- Vite dev proxy: `/api` and `/ws` -> `http://localhost:8000` (`server.proxy` in vite.config).
- Plotly bundle is fat - dynamic import `LightCurve` so first paint stays fast.
- Never hardcode agent colors in two places; single map in `theme.ts`.
