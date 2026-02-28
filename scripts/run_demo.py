from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import json

from common.config import load_config
from evidence_fusion.fusion import align_entities, fuse_relations
from information_extraction.ner_re import MorphologyAwareExtractor
from knowledge_graph.builder import build_nodes
from knowledge_graph.store import InMemoryKG
from literature_retrieval.pipeline import retrieve_evidence
from reasoning.service import query_reasoning


def main() -> None:
    cfg = load_config()
    evidence = retrieve_evidence(cfg)

    extractor = MorphologyAwareExtractor(cfg["extraction"]["dictionary_path"])
    entities = []
    relations = []
    for ev in evidence:
        ents = extractor.extract_entities(ev)
        rels = extractor.extract_relations(ev, ents)
        entities.extend(ents)
        relations.extend(rels)

    emap = align_entities(entities)
    edges = fuse_relations(relations, emap)

    kg = InMemoryKG()
    kg.upsert_nodes(build_nodes(entities))
    kg.upsert_edges(edges)

    query = "L型糖 vs D型糖 是否具有免疫调节作用？给出证据链"
    paths = query_reasoning(kg.graph, query, top_k=5, cfg=cfg)
    print(json.dumps({"query": query, "paths": paths}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
