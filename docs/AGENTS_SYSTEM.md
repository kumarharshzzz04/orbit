# docs/AGENTS_SYSTEM.md - The Six-Agent Core (Owner: A)

MiroFish-inspired: persistent personas + shared graph memory + a synthesis step -
but the arena is science. Agents produce structured research artifacts and every
claim must pass a benchmark gate. Agents are thin Python classes: role prompt +
tools + JSON output contract. Personality lives in the prompt; memory in SQLite.

## Roster

| Agent | Question | Reads | Writes | Temp |
|---|---|---|---|---|
| Orchestrator | What happens next? | registry, graph | mission plan, round budget | 0.2 |
| Researcher | What is known? | papers, prior runs | evidence cards w/ citations | 0.3 |
| Hypothesizer | What should we try? | evidence cards | experiment proposal (JSON) | 0.7 |
| Skeptic | Why will this fail? | proposals, data cards | critique: veto or pass | 0.4 |
| Experimenter | What happens if we test? | approved proposal | run record + metrics | 0.1 |
| Evaluator | Did it improve? | champion + run record | verdict: KEEP/REJECT + rationale | 0.1 |

## The loop (max 2 revision rounds per mission)

1. Orchestrator frames the mission
2. Researcher -> evidence cards (papers corpus + graph query, MUST cite)
3. Hypothesizer -> ONE-change proposal vs current champion (config JSON + expected gain)
4. Skeptic checks: leakage across stars, fold artifacts, class imbalance, injection
   noise overfit -> VETO (with reason + fix) or PASS
5. Experimenter executes exactly (no improvisation) in the ML sandbox subprocess
6. Evaluator applies the gate -> verdict card (numbers + plain-language rationale)
7. Orchestrator records verdict + broadcasts; graph writes nodes/edges at every step

## Message schema (contract - see AGENTS.md 3.1)

```json
{ "agent": "researcher", "round": 1, "type": "evidence_card",
  "body": "...", "refs": ["KOI-7.01", "paper:latham2011"] }
```

`type` enum: evidence_card | proposal | critique | run_record | verdict | status.
A CI test replays canned transcripts through the orchestrator and asserts schema
compliance - a prompt edit that breaks the protocol fails the pipeline.

## Prompt rules that keep the demo honest

- Every prompt < 120 words; role + rules + output schema, nothing else.
- JSON mode ON; schema in the prompt; one re-ask on parse failure, then fallback text.
- Researcher MUST cite ids; uncited claims get bounced by the Orchestrator.
- Hypothesizer: exactly ONE change vs champion, must state expected gain.
- Skeptic veto template: [risk] + [why it applies here] + [fix or kill].
- Experimenter: zero LLM creativity - it may only format and execute.
- Evaluator: numbers first, prose second; REJECT always includes a diagnosis line.

## LLM connector (provider-agnostic)

One module reads `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` and speaks the
OpenAI-compatible protocol. Tested on Day 0 with: a cheap cloud model, a second
provider, and Ollama local. `LLM_MODE=mock` replays canned responses for tests
and offline demos. Final fallback: transcript replay over WS (demo survives total
network death).

## Knowledge graph (lightweight)

SQLite `graph_edges` (src_type, src_id, rel, dst_type, dst_id) + NetworkX in memory.
Node types: paper, dataset, hypothesis, experiment, verdict. Edges: CITES, PROPOSES,
EVALUATES, BEAT, REJECTED_BY, DERIVED_FROM. Powers Researcher queries and the
(stretch) graph panel via GET /api/graph.
