from __future__ import annotations

import json
from pathlib import Path

from common.types import EvidenceUnit
from literature_retrieval.pubmed_client import PubMedRetriever, to_evidence_units


def load_demo_evidence(path: str = "data/demo_data/demo_evidence.json") -> list[EvidenceUnit]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [EvidenceUnit(**item) for item in data]


def retrieve_evidence(config: dict) -> list[EvidenceUnit]:
    if config["project"].get("demo_mode", True):
        return load_demo_evidence()

    retriever = PubMedRetriever(
        email=config["retrieval"]["email"],
        tool=config["retrieval"]["tool"],
        use_api=config["retrieval"].get("use_pubmed_api", True),
    )
    pmids: list[str] = []
    for term in config["retrieval"]["query_terms"]:
        pmids.extend(retriever.search_pmids(term, retmax=config["retrieval"]["max_articles"]))
    pmids = list(dict.fromkeys(pmids))[: config["retrieval"]["max_articles"]]
    return to_evidence_units(retriever.fetch_summaries(pmids))
