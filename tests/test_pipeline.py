from common.config import load_config
from evidence_fusion.fusion import align_entities, fuse_relations
from information_extraction.ner_re import MorphologyAwareExtractor
from knowledge_graph.builder import build_nodes
from knowledge_graph.store import InMemoryKG
from literature_retrieval.pipeline import retrieve_evidence
from reasoning.service import query_reasoning


def test_end_to_end_demo_pipeline():
    cfg = load_config()
    evidence = retrieve_evidence(cfg)
    assert len(evidence) >= 2

    extractor = MorphologyAwareExtractor(cfg["extraction"]["dictionary_path"])
    entities, relations = [], []
    for ev in evidence:
        ents = extractor.extract_entities(ev)
        rels = extractor.extract_relations(ev, ents)
        entities.extend(ents)
        relations.extend(rels)

    assert any(e.entity_type == "glycan" for e in entities)
    assert any(r.relation == "associated_with_phenotype" for r in relations)

    kg = InMemoryKG()
    kg.upsert_nodes(build_nodes(entities))
    kg.upsert_edges(fuse_relations(relations, align_entities(entities)))
    paths = query_reasoning(kg.graph, "L型糖 vs D型糖 是否具有免疫调节作用", 5, cfg)
    assert len(paths) >= 1
    assert "nodes" in paths[0]
