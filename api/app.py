from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI
from pydantic import BaseModel, Field

from common.config import load_config
from evidence_fusion.fusion import align_entities, fuse_relations
from information_extraction.ner_re import MorphologyAwareExtractor
from knowledge_graph.builder import build_nodes
from knowledge_graph.store import InMemoryKG
from literature_retrieval.pipeline import retrieve_evidence
from reasoning.service import query_reasoning

app = FastAPI(title="Glycan Immune KG API")


class QueryRequest(BaseModel):
    query: str = Field(..., description="自然语言查询")
    species: str | None = None
    experimental_system: str | None = None
    immune_phenotype: str | None = None
    time_range: str | None = None
    top_k: int = 5


@app.on_event("startup")
def startup_event() -> None:
    cfg = load_config()
    extractor = MorphologyAwareExtractor(cfg["extraction"]["dictionary_path"])
    evidence = retrieve_evidence(cfg)
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

    app.state.cfg = cfg
    app.state.evidence = [asdict(x) for x in evidence]
    app.state.graph = kg.graph


@app.post("/query")
def query(req: QueryRequest) -> dict:
    results = query_reasoning(app.state.graph, req.query, req.top_k, app.state.cfg)
    return {
        "query": req.query,
        "filters": req.model_dump(exclude={"query", "top_k"}),
        "top_k": req.top_k,
        "results": results,
    }
