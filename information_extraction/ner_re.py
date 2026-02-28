from __future__ import annotations

import re
from pathlib import Path

import json

from common.types import EntityMention, EvidenceUnit, MorphologySlots, RelationMention


class MorphologyAwareExtractor:
    def __init__(self, dictionary_path: str):
        self.lexicon = json.loads(Path(dictionary_path).read_text(encoding="utf-8"))

    def extract_entities(self, evidence: EvidenceUnit) -> list[EntityMention]:
        text = evidence.text
        mentions: list[EntityMention] = []
        for etype in ["glycan", "receptor", "pathway", "phenotype", "condition"]:
            for term in self.lexicon.get(etype, []):
                for m in re.finditer(re.escape(term), text, flags=re.IGNORECASE):
                    morph = self._extract_morphology(term + " " + text) if etype == "glycan" else None
                    mentions.append(
                        EntityMention(
                            entity_id=f"{etype}:{term.lower().replace(' ', '_')}",
                            evidence_id=evidence.evidence_id,
                            text=m.group(0),
                            entity_type=etype,
                            normalized_name=term,
                            start=m.start(),
                            end=m.end(),
                            morphology=morph,
                            confidence=0.75,
                        )
                    )
        return mentions

    def _extract_morphology(self, text: str) -> MorphologySlots:
        patterns = self.lexicon.get("morph_patterns", {})
        slots = MorphologySlots()
        for cfg, triggers in patterns.get("configuration", {}).items():
            if any(t.lower() in text.lower() for t in triggers):
                slots.configuration = cfg
        for ano, triggers in patterns.get("anomer", {}).items():
            if any(t.lower() in text.lower() for t in triggers):
                slots.anomer = ano
        for mod, triggers in patterns.get("modification", {}).items():
            if any(t.lower() in text.lower() for t in triggers):
                slots.modification = mod
        if not slots.configuration:
            slots.uncertainty.append("missing_configuration")
        return slots

    def extract_relations(self, evidence: EvidenceUnit, entities: list[EntityMention]) -> list[RelationMention]:
        by_type: dict[str, list[EntityMention]] = {}
        for e in entities:
            by_type.setdefault(e.entity_type, []).append(e)
        rels: list[RelationMention] = []
        for g in by_type.get("glycan", []):
            for r in by_type.get("receptor", []):
                rels.append(self._relation(g.entity_id, "binds_receptor", r.entity_id, evidence.evidence_id, g))
            for p in by_type.get("pathway", []):
                rel_name = "activates_pathway" if "activat" in evidence.text.lower() else "modulates_pathway"
                rels.append(self._relation(g.entity_id, rel_name, p.entity_id, evidence.evidence_id, g))
            for ph in by_type.get("phenotype", []):
                rels.append(self._relation(g.entity_id, "associated_with_phenotype", ph.entity_id, evidence.evidence_id, g))
            if g.morphology and g.morphology.configuration:
                rels.append(
                    RelationMention(
                        head_id=g.entity_id,
                        relation="has_configuration",
                        tail_id=f"morph_config:{g.morphology.configuration}",
                        evidence_id=evidence.evidence_id,
                        confidence=0.8,
                        uncertainty_reasons=list(g.morphology.uncertainty),
                    )
                )
        return rels

    def _relation(self, h: str, r: str, t: str, ev_id: str, glycan: EntityMention) -> RelationMention:
        conf = 0.7
        reasons: list[str] = []
        if glycan.morphology and glycan.morphology.configuration == "D" and "anti-inflammatory" in t:
            conf -= 0.2
            reasons.append("morphology_consistency_penalty:D_vs_anti-inflammatory")
        if glycan.morphology and not glycan.morphology.configuration:
            conf -= 0.1
            reasons.append("missing_configuration")
        return RelationMention(head_id=h, relation=r, tail_id=t, evidence_id=ev_id, confidence=max(conf, 0.1), uncertainty_reasons=reasons)
