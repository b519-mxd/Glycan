"""Deterministic quality-event coordination prototype for GlycoPath.

Scope: controlled state, type-specific gates, bounded tool dispatch, dependency
invalidation and audit. NOT an LLM-driven adaptive-planning experiment, a
validated scientific evidence model, or proof of multi-agent superiority.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Callable, Mapping


def _digest(data: Mapping) -> str:
    return sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Artifact:
    aid: str
    kind: str  # entity | relation | path
    payload: dict
    parents: tuple[str, ...] = ()
    revision: int = 1
    stale: bool = False
    fingerprint: str = ""


@dataclass(frozen=True)
class Gate:
    state: str  # PASS | REVIEW | BLOCK
    code: str
    reason: str


@dataclass(frozen=True)
class Patch:
    aid: str
    payload: dict


@dataclass(frozen=True)
class Route:
    agent: str
    cost: int = 1


@dataclass
class KnowledgeState:
    artifacts: dict[str, Artifact] = field(default_factory=dict)

    def put(self, aid: str, kind: str, payload: dict,
            parents: tuple[str, ...] = ()) -> bool:
        """Commit one object; invalidate its transitive dependents when changed.

        This does NOT certify the scientific correctness of its payload.
        """
        if kind not in {"entity", "relation", "path"}:
            raise ValueError("UNSUPPORTED_KIND")
        parents = tuple(parents)
        if len(set(parents)) != len(parents) or aid in parents:
            raise ValueError("INVALID_DEPENDENCIES")
        if any(x not in self.artifacts for x in parents):
            raise ValueError("MISSING_DEPENDENCY")
        old = self.artifacts.get(aid)
        if old and (old.kind != kind or old.parents != parents):
            raise ValueError("IMMUTABLE_IDENTITY_OR_PARENT_SET")
        new_payload = deepcopy(payload)
        fp = _digest(new_payload)
        if old and old.fingerprint == fp and not old.stale:
            return False
        # Newly refreshed content becomes non-stale; quality gate evaluates
        # whether parent states and content are permissible.
        self.artifacts[aid] = Artifact(aid, kind, new_payload, parents,
                                       (old.revision + 1 if old else 1), False, fp)
        self._invalidate_descendants(aid)
        return True

    def _invalidate_descendants(self, aid: str) -> None:
        impacted = {aid}
        while True:
            new = {k for k, obj in self.artifacts.items()
                   if k not in impacted and any(p in impacted for p in obj.parents)}
            if not new:
                break
            impacted |= new
        for child in impacted - {aid}:
            obj = self.artifacts[child]
            self.artifacts[child] = Artifact(obj.aid, obj.kind, deepcopy(obj.payload),
                                              obj.parents, obj.revision, True,
                                              obj.fingerprint)

    def gate(self, aid: str) -> Gate:
        obj = self.artifacts[aid]
        if obj.stale:
            return Gate("REVIEW", "STALE_DEPENDENCY", "Upstream object revised")
        # This rule has precedence over local checks to ensure that repairing
        # a parent is attempted before rebuilding a dependent object.
        if any(self.gate(p).state != "PASS" for p in obj.parents):
            return Gate("REVIEW", "UPSTREAM_NOT_PASS", "Upstream evidence unresolved")
        d = obj.payload
        if obj.kind == "entity":
            s = d.get("structure_status")
            if s == "CONFLICT":
                return Gate("BLOCK", "STRUCTURE_CONFLICT", "Conflicting chemical structures")
            if s != "VERIFIED" or not d.get("registry_id"):
                return Gate("REVIEW", "STRUCTURE_UNRESOLVED", "Identity lacks verified accession")
            return Gate("PASS", "OK", "Identity marker verified by supplied tool evidence")
        if obj.kind == "relation":
            if not d.get("evidence_ids") or not d.get("source_id"):
                return Gate("REVIEW", "MISSING_PROVENANCE", "Source or evidence key unavailable")
            if d.get("context_status") == "CONFLICT":
                return Gate("BLOCK", "CONTEXT_CONFLICT", "Known critical condition mismatch")
            if d.get("context_status") != "MATCH":
                return Gate("REVIEW", "CONTEXT_UNRESOLVED", "Unknown context is not compatible")
            if d.get("polarity") not in (-1, 0, 1):
                return Gate("BLOCK", "INVALID_POLARITY", "Evidence polarity invalid")
            return Gate("PASS", "OK", "Traceable condition-matched evidence")
        if obj.kind == "path":
            if not d.get("relation_ids") or tuple(d["relation_ids"]) != obj.parents:
                return Gate("BLOCK", "INVALID_PATH", "Relation list and dependencies differ")
            if any(self.artifacts[p].kind != "relation" for p in obj.parents):
                return Gate("BLOCK", "INVALID_PATH", "Path parents must be relations")
            if d.get("direction_status") == "CONFLICT":
                return Gate("BLOCK", "DIRECTION_CONFLICT", "Invalid directed traversal")
            if d.get("direction_status") != "VERIFIED":
                return Gate("REVIEW", "PATH_UNRESOLVED", "Direction requires review")
            return Gate("PASS", "OK", "Local structural / evidence gates passed; not a causal claim")
        raise AssertionError("Unreachable")

    def issues(self) -> list[tuple[str, Gate]]:
        """Topological issues, parents first; deterministic tie-breaking."""
        def depth(aid: str) -> int:
            x = self.artifacts[aid]
            return 0 if not x.parents else 1 + max(depth(p) for p in x.parents)
        return [(aid, g) for aid in sorted(self.artifacts,
                 key=lambda a: (depth(a), a)) if (g := self.gate(aid)).state != "PASS"]

    def snapshot(self) -> dict[str, Artifact]:
        return deepcopy(self.artifacts)


class AdaptiveCoordinator:
    """Quality-driven *deterministic* tool selection with a strict call budget.

    Handler signature: (artifact_copy, full_snapshot, gate) -> Patch | None.
    No model/LLM uses or supplies an unverified scientific probability.
    """
    def __init__(self, state: KnowledgeState,
                 routes: dict[tuple[str, str], Route],
                 agents: dict[str, Callable[[Artifact, dict[str, Artifact], Gate], Patch | None]],
                 budget: int = 8, max_attempts_per_issue: int = 2):
        if budget < 0 or max_attempts_per_issue < 1:
            raise ValueError("INVALID_BUDGET")
        if any(x.cost < 1 for x in routes.values()):
            raise ValueError("INVALID_COST")
        if any(x.agent not in agents for x in routes.values()):
            raise ValueError("NON_ALLOWLISTED_AGENT")
        self.state, self.routes, self.agents = state, routes, agents
        self.budget, self.max_attempts = budget, max_attempts_per_issue
        self.log: list[dict] = []
        self.attempts: dict[tuple[str, str], int] = {}

    def run(self) -> dict:
        used = 0
        exhausted = False
        while True:
            actionable = []
            for aid, gate in self.state.issues():
                key = (aid, gate.code)
                if gate.code == "UPSTREAM_NOT_PASS":
                    continue
                route = self.routes.get((self.state.artifacts[aid].kind, gate.code))
                if route and self.attempts.get(key, 0) < self.max_attempts:
                    actionable.append((aid, gate, route))
            if not actionable:
                break
            aid, gate, route = actionable[0]
            if used + route.cost > self.budget:
                exhausted = True
                break
            used += route.cost
            key = (aid, gate.code)
            self.attempts[key] = self.attempts.get(key, 0) + 1
            before = self.state.artifacts[aid]
            entry = {"artifact": aid, "issue": gate.code, "agent": route.agent,
                     "attempt": self.attempts[key], "cost": route.cost,
                     "previous_revision": before.revision}
            try:
                proposed = self.agents[route.agent](deepcopy(before),
                                                       self.state.snapshot(), gate)
                if proposed is None:
                    entry["result"] = "NO_CHANGE"
                elif not isinstance(proposed, Patch) or proposed.aid != aid:
                    raise ValueError("CROSS_ARTIFACT_WRITE_FORBIDDEN")
                else:
                    changed = self.state.put(aid, before.kind, proposed.payload,
                                             before.parents)
                    entry["result"] = "UPDATED" if changed else "NO_CHANGE"
                    entry["new_revision"] = self.state.artifacts[aid].revision
                    entry["new_gate"] = self.state.gate(aid).code
            except Exception as exc:
                entry["result"] = "REJECTED"
                entry["reason"] = type(exc).__name__
            self.log.append(entry)
        return {
            "used_budget": used, "budget": self.budget,
            "budget_exhausted": exhausted,
            "gate_statuses": {x: self.state.gate(x).state
                              for x in sorted(self.state.artifacts)},
            "unresolved": [{"artifact": aid, "code": g.code, "state": g.state}
                           for aid, g in self.state.issues()],
            "audit_log": deepcopy(self.log),
            "revisions": {aid: obj.revision for aid, obj in self.state.artifacts.items()},
        }
