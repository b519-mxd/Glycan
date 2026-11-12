"""Source-dependency and context aware signed evidence index (NOT probability)."""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Mapping

@dataclass(frozen=True)
class Claim:
    head: str
    relation: str
    tail: str
    document_id: str
    evidence_id: str
    polarity: int
    context: Mapping[str, str] = field(default_factory=dict)
    original_experiment_id: str | None = None
    quality: float = 1.0
    source_quote: str = ""
    def __post_init__(self):
        if self.polarity not in (-1, 0, 1):
            raise ValueError("Invalid polarity")
        if not 0 <= self.quality <= 1:
            raise ValueError("Invalid quality")
        if not self.document_id or not self.evidence_id:
            raise ValueError("Source identifiers required")

def context_key(context: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(k).strip().lower(), str(v).strip().lower()) for k,v in context.items() if v))

def source_group_key(c: Claim) -> str:
    return "experiment:" + c.original_experiment_id if c.original_experiment_id else "document:" + c.document_id

def fuse_claims(claims: list[Claim]) -> list[dict]:
    strata = defaultdict(list)
    for c in claims:
        strata[(c.head,c.relation,c.tail,context_key(c.context))].append(c)
    result = []
    for (h,r,t,context), group in sorted(strata.items()):
        sources = defaultdict(list)
        for c in group:
            sources[source_group_key(c)].append(c)
        clusters = []
        for key, records in sorted(sources.items()):
            denom = sum(c.quality for c in records)
            signed = sum(c.polarity*c.quality for c in records)/denom if denom else 0.
            clusters.append((key,max(c.quality for c in records),signed,len(records)))
        denom = sum(q for _,q,_,_ in clusters)
        score = sum(q*p for _,q,p,_ in clusters)/denom if denom else 0.
        result.append({"head":h,"relation":r,"tail":t,"context":dict(context),
          "support_index":round(score,6),"is_calibrated_probability":False,
          "independent_source_groups":len(clusters),"mention_count":len(group),
          "source_groups":[{"id":s,"weight":q,"signed_polarity":round(p,6),"records":n} for s,q,p,n in clusters],
          "provenance":[c.evidence_id for c in group],
          "has_opposing_reports":any(c.polarity==1 for c in group) and any(c.polarity==-1 for c in group)})
    return result

def audit_path(edges: list[dict]) -> dict:
    issues = []
    for i,e in enumerate(edges):
        if not e.get("provenance"):
            issues.append({"edge":i,"type":"MISSING_PROVENANCE"})
        if e.get("structure_status") == "CONFLICT":
            issues.append({"edge":i,"type":"CHEMICAL_CONFLICT"})
        if e.get("evidence_status") not in ("OBSERVED","EXPERIMENTALLY_VERIFIED"):
            issues.append({"edge":i,"type":"NOT_EXPERIMENTAL_OBSERVATION"})
    contexts = [dict(context_key(e.get("context") or {})) for e in edges]
    for i in range(1,len(edges)):
        a,b = contexts[i-1],contexts[i]
        if any(a[k]!=b[k] for k in a.keys() & b.keys()):
            issues.append({"edge":i,"type":"CONTEXT_MISMATCH"})
    return {"status":"CANDIDATE_NEEDS_REVIEW" if issues else "LOCALLY_SUPPORTED_NOT_CAUSALLY_VERIFIED",
      "issues":issues,"edge_count":len(edges)}
