from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceUnit:
    evidence_id: str
    doc_id: str
    pmid: str | None
    url: str | None
    section: str
    paragraph_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MorphologySlots:
    configuration: str | None = None  # L/D
    anomer: str | None = None  # alpha/beta
    linkage: str | None = None
    branch: str | None = None
    modification: str | None = None
    uncertainty: list[str] = field(default_factory=list)


@dataclass
class EntityMention:
    entity_id: str
    evidence_id: str
    text: str
    entity_type: str
    normalized_name: str
    start: int
    end: int
    morphology: MorphologySlots | None = None
    confidence: float = 0.5


@dataclass
class RelationMention:
    head_id: str
    relation: str
    tail_id: str
    evidence_id: str
    confidence: float
    uncertainty_reasons: list[str] = field(default_factory=list)


@dataclass
class EdgeConfidenceBreakdown:
    evidence_quality: float
    repeatability: float
    condition_comparability: float
    source_diversity: float
    morphology_consistency: float


@dataclass
class KGNode:
    node_id: str
    label: str
    node_type: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class KGEdge:
    source: str
    relation: str
    target: str
    confidence: float
    provenance: list[dict[str, Any]] = field(default_factory=list)
    features: EdgeConfidenceBreakdown | None = None


@dataclass
class ReasoningPath:
    nodes: list[str]
    relations: list[str]
    edge_scores: list[float]
    total_score: float
    confidence_breakdown: dict[str, float]
    evidence_chain: list[dict[str, Any]]
    explanation: str
