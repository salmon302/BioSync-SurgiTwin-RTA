Title: G1.8 boundary wording and SOUP version cells aligned with recorded evidence
Date: 2026-10-14T22:00:00Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: residue from SNDEV/docs/impl-2026-10-14-post-kickoff-cleanup.md (left-stale items)
Summary: Replaces an unsupported causal claim in the G1.8 PASS boundary and two SOUP Version cells that conflicted with their Pin status cells. Documentation only.

## Task Reference

Left-stale items from SNDEV/docs/impl-2026-10-14-post-kickoff-cleanup.md. Evidence source: SNDEV/docs/impl-2026-10-14-g18-1m-row-run.md (Finding 1).

## Specification Summary

1. DEVELOPMENT_PLAN.md, Phase 1 Verification Gates table, G1.8 row: the boundary (a) clause stated as established that broadcast fan-out serialization causes the 50 ms bound failure. The run record says the tail-latency source was not isolated. Restate the clause to name the relay serialization as observed and the cause as unisolated, with client-side queueing as an unmeasured candidate.
2. sim/SOUP.md, two Version cells (websockets and Locust): the Version cells said "observed" and "not pinned", which conflicted with the Pin status cells updated in commit 06f5f16. State the pin in vv/tests/PQ/requirements.txt.

## Implementation Notes

### Edit 1: DEVELOPMENT_PLAN.md, G1.8 row, boundary (a)

Old:
`the 50 ms bound fails at 20 points per second and above on this host because of broadcast fan-out serialization; (b)`

New:
`the 50 ms bound fails at 20 points per second and above on this host; the relay serializes broadcast fan-out per frame (\`ConnectionManager.broadcast\`) and the tail-latency source was not isolated (client-side queueing in the single client process is an unmeasured candidate); (b)`

Only this clause changed. The G1.8 Acceptance Metric cell is unchanged.

### Edit 2: sim/SOUP.md, websockets Version cell (line 31)

Old: `17.2 observed. Not pinned directly. Pulled in through \`uvicorn[standard]\`.`

New: `17.2, pinned in \`vv/tests/PQ/requirements.txt\` (still pulled transitively through \`uvicorn[standard]\` in the middleware venvs).`

### Edit 3: sim/SOUP.md, Locust Version cell (line 33)

Old: `2.46.7 observed in \`.venv-pq-load\`. Not pinned in a tracked file.`

New: `2.46.7, pinned in \`vv/tests/PQ/requirements.txt\` (installed in \`.venv-pq-load\`).`

### Files changed

* DEVELOPMENT_PLAN.md (1 line)
* sim/SOUP.md (2 lines)
* SNDEV/docs/impl-2026-10-14-g18-wording-fix.md (this log, new)

### Out of scope

SNDEV/docs/impl-2026-10-14-phase1-closure.md line 18 contains the same causal phrasing ("because of broadcast fan-out serialization"). It is not owned by this change and was not edited.

## Verification

| Check | Result |
|---|---|
| Old DEVELOPMENT_PLAN.md clause absent (grep, literal "because of broadcast fan-out serialization; (b)") | PASS |
| Old SOUP.md Version strings absent (grep, "17.2 observed. Not pinned directly", "2.46.7 observed in `.venv-pq-load`. Not pinned") | PASS |
| New clause appears exactly once in DEVELOPMENT_PLAN.md | PASS |
| New websockets and Locust Version strings each appear exactly once in sim/SOUP.md | PASS |
| git diff touches only DEVELOPMENT_PLAN.md, sim/SOUP.md, and this log | PASS |
| Acceptance Metric and gate-metric text unchanged (diff shows 1 line in DEVELOPMENT_PLAN.md, the G1.8 row, with only the boundary clause differing) | PASS |
| Banned-word sweep (AGENTS.md section 1 list, case-insensitive) on inserted text in both edited files | PASS (0 matches in both files) |
| Em dash, en dash, curly quote sweep (both files) | PASS (0 matches) |
| Tests | Not run (documentation only, per task scope) |
