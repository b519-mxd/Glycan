from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from common.types import EvidenceUnit

logger = logging.getLogger(__name__)


class PubMedRetriever:
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, email: str, tool: str, use_api: bool = True):
        self.email = email
        self.tool = tool
        self.use_api = use_api

    def _get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def search_pmids(self, term: str, retmax: int = 5) -> list[str]:
        if not self.use_api:
            return []
        params = {
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": retmax,
            "tool": self.tool,
            "email": self.email,
        }
        return self._get_json("esearch.fcgi", params).get("esearchresult", {}).get("idlist", [])

    def fetch_summaries(self, pmids: list[str]) -> list[dict[str, Any]]:
        if not pmids or not self.use_api:
            return []
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
            "tool": self.tool,
            "email": self.email,
        }
        result = self._get_json("esummary.fcgi", params).get("result", {})
        return [result[p] for p in pmids if p in result]


def to_evidence_units(summaries: list[dict[str, Any]]) -> list[EvidenceUnit]:
    units: list[EvidenceUnit] = []
    for s in summaries:
        pmid = str(s.get("uid"))
        title = s.get("title", "")
        snippet = s.get("elocationid", "")
        text = f"{title}. {snippet}".strip()
        units.append(
            EvidenceUnit(
                evidence_id=f"PMID:{pmid}:abs:0",
                doc_id=f"PMID:{pmid}",
                pmid=pmid,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                section="abstract",
                paragraph_id="0",
                text=text,
                metadata={"source": "pubmed"},
            )
        )
    return units
