# HANDOVER.md - Module Handover Records

Fill one block **before leaving the keyboard** whenever a module changes hands -
even mid-day, even for one hour. Four questions, no essays. Newest at top.

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
