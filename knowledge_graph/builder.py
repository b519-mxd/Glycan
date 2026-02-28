from __future__ import annotations

from common.types import EntityMention, KGNode


def build_nodes(entities: list[EntityMention]) -> list[KGNode]:
    seen = {}
    for e in entities:
        if e.entity_id not in seen:
            props = {"mentions": [e.text], "confidence": e.confidence}
            if e.morphology:
                props["morphology"] = e.morphology.__dict__
            seen[e.entity_id] = KGNode(node_id=e.entity_id, label=e.normalized_name, node_type=e.entity_type, properties=props)
            if e.morphology and e.morphology.configuration:
                m_id = f"morph_config:{e.morphology.configuration}"
                seen[m_id] = KGNode(node_id=m_id, label=e.morphology.configuration, node_type="morph_slot", properties={})
    return list(seen.values())
