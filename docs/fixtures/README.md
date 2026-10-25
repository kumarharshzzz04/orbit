# Handoff fixtures

These files let A, B and D build against the same shapes before the backend and
frontend exist. They are examples, not production data.

| File | Consumer | Purpose |
|---|---|---|
| `ws_events.jsonl` | D (frontend), A (orchestrator) | A complete mock mission stream using the AGENTS.md 3.1 envelope |
| `registry_rows.example.json` | B (registry), A (evaluator) | Three finalized rows: seed champion, KEEP challenger, REJECT challenger |
| `proposal.example.json` | A (hypothesizer/experimenter) | One-change proposal against the seed champion |

## Replay the WebSocket stream

Each line is one frame. A minimal frontend harness can read the file, parse each
line, and dispatch it exactly as `useMissionSocket` would after a real socket
message:

```ts
for (const line of text.split("\n")) {
  if (!line.trim()) continue;
  const frame = JSON.parse(line);
  store.dispatch(frame);
}
```

`verdict.payload.kept` is the only promotion decision on the wire. The rationale
is for humans; the registry row is the durable record.

## Registry rows

The rows carry the AGENTS.md 3.2 fields. `verdict` is already finalized here so
the UI has something to render; the real ML sandbox always emits `PENDING` and
only `services/registry.promote()` may change it.

## Proposal

`proposal.example.json` is the known-good CP-2 demo proposal: switch the
champion from `catalog_v1` to `vetting_v1`. It produced F1 0.9305 on the frozen
stub split, versus 0.8372 for the seed champion. The Experimenter should load
`base_config`, apply exactly one change, validate the result with
`RunConfig.from_dict`, then run the CLI.
