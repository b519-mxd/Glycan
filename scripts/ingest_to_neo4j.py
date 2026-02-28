from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from common.config import load_config
from evidence_fusion.fusion import align_entities, fuse_relations
from information_extraction.ner_re import MorphologyAwareExtractor
from knowledge_graph.builder import build_nodes
from knowledge_graph.store import Neo4jKG
from literature_retrieval.pipeline import retrieve_evidence


def main() -> None:
    cfg = load_config()
    extractor = MorphologyAwareExtractor(cfg["extraction"]["dictionary_path"])
    evidence = retrieve_evidence(cfg)
    entities, relations = [], []
    for ev in evidence:
        ents = extractor.extract_entities(ev)
        rels = extractor.extract_relations(ev, ents)
        entities.extend(ents)
        relations.extend(rels)

    nodes = build_nodes(entities)
    edges = fuse_relations(relations, align_entities(entities))

    kg = Neo4jKG(cfg["knowledge_graph"]["neo4j_uri"], cfg["knowledge_graph"]["neo4j_user"], cfg["knowledge_graph"]["neo4j_password"])
    kg.init_schema()
    kg.upsert_nodes(nodes)
    kg.upsert_edges(edges)
    kg.close()


if __name__ == "__main__":
    main()
