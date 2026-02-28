from __future__ import annotations

from collections import defaultdict

from common.types import EdgeConfidenceBreakdown, EntityMention, KGEdge, RelationMention


ALIASES = {
    "dcsign": "DC-SIGN",
    "nfkb": "NF-kB",
    "l type monosaccharide": "L-type monosaccharide",
    "d type monosaccharide": "D-type monosaccharide",
}


def normalize_name(name: str) -> str:
    key = name.lower().replace("-", "").strip()
    return ALIASES.get(key, name)


def align_entities(entities: list[EntityMention]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for e in entities:
        mapping[e.entity_id] = f"{e.entity_type}:{normalize_name(e.normalized_name).lower().replace(' ', '_')}"
    return mapping


def fuse_relations(relations: list[RelationMention], entity_mapping: dict[str, str]) -> list[KGEdge]:
    grouped: dict[tuple[str, str, str], list[RelationMention]] = defaultdict(list)
    for rel in relations:
        h = entity_mapping.get(rel.head_id, rel.head_id)
        t = entity_mapping.get(rel.tail_id, rel.tail_id)
        grouped[(h, rel.relation, t)].append(rel)

    edges: list[KGEdge] = []
    for (h, r, t), rels in grouped.items():
        confs = [x.confidence for x in rels]
        morphology_consistency = 1.0 - (sum("morphology" in " ".join(x.uncertainty_reasons) for x in rels) / max(len(rels), 1))
        breakdown = EdgeConfidenceBreakdown(
            evidence_quality=min(1.0, 0.5 + 0.1 * len(rels)),
            repeatability=min(1.0, len(rels) / 3),
            condition_comparability=0.7,
            source_diversity=min(1.0, len({x.evidence_id.split(':')[1] for x in rels}) / 2),
            morphology_consistency=morphology_consistency,
        )
        final_conf = (sum(confs) / len(confs)) * (0.6 + 0.4 * morphology_consistency)
        edges.append(
            KGEdge(
                source=h,
                relation=r,
                target=t,
                confidence=round(final_conf, 3),
                provenance=[{"evidence_id": x.evidence_id, "uncertainty_reasons": x.uncertainty_reasons} for x in rels],
                features=breakdown,
            )
        )
    return edges
