# GlycoPath: quality-feedback coordination research prototype

Status: **controlled software verification; NOT end-to-end multi-agent evidence**.

## Scope and audited inputs

- Independent branch based on `glycopath/methods-extension-20261112` (`63c50ca103665ea731487b4ace8cd56f6f535d37`).
- `glycopath_research/supervisor.py` in the base supports static Plan validation, dependencies, bounded same-tool retry and PASS/REVIEW/BLOCK gates. It does **not** implement issue-specific cross-agent replanning.
- New `glycopath_research/quality_feedback.py` is an **additive** deterministic coordinator, without altering original training, evaluation, or research results.

## Implemented rules

1. Shared typed artifacts (`entity`, `relation`, `path`) with immutable IDs and dependency sets, per-artifact revisions, content fingerprints and deep-copied payloads.
2. Topologically prioritized local gates: chemical conflict (`BLOCK`), unknown identity (`REVIEW`), missing provenance (`REVIEW`), context conflict (`BLOCK`), unknown context (`REVIEW`), incompatible path direction (`BLOCK`). Gate PASS means only **local rule compliance**, NOT independently verified scientific truth.
3. Upstream correction recursively invalidates dependent relation and path objects. Such objects are not accepted until refreshed using their registered dependencies.
4. Issue-to-agent routing via allowlisted handlers, with fixed positive costs, a total budget, maximum attempts for each issue, action audit and rejection of cross-artifact writes.
5. Deterministic no-LLM fallback: if no applicable authorized repair exists, the item is left unresolved; no guessed chemical identities, citations, or experimental claims are generated.

## Explicitly NOT implemented or NOT supported by these results

- No real LLM inference during these tests, and no proof that an LLM plan adapts to quality events.
- No real retrieval of missing glycan linkages or study origins. Test agents receive synthetic `demo:` IDs that are intentionally not scientific evidence.
- No independent verification that a claimed `registry_id` is chemically valid: the gate checks schema and declared states only. A production adapter must verify accession and chemical graph against authoritative registry records.
- No literature-to-GKG end-to-end execution, no independent scientific path correctness assessment and no multi-agent superiority experiment.
- Tests validate the control layer alone; existing Qwen, glycan graph and IRRL numbers remain unchanged.

## Program check

```bash
python -m unittest discover -s tests -p test_quality_feedback.py -v
```

14 tests should pass. Only after the real retrieval/identity/evidence connectors and paired query-level comparison are added should this mechanism be described as a validated autonomous multi-agent discovery method.

## Next scientific evaluation

A paired test with identical sources/tools and bounded compute compares:
Single LLM tool user, fixed pipeline, multi-agent without feedback, complete feedback-gated multi-agent. Record per-query errors, blocked knowledge, repairs, verified citations, accepted hypothesis paths, tool calls, latency and token costs. Use independent gold labels and avoid using schema-gate PASS as scientific correctness.
