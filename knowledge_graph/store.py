from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from common.graph import SimpleMultiDiGraph
from common.types import KGEdge, KGNode


class InMemoryKG:
    def __init__(self):
        self.graph = SimpleMultiDiGraph()

    def upsert_nodes(self, nodes: Iterable[KGNode]) -> None:
        for n in nodes:
            self.graph.add_node(n.node_id, label=n.label, node_type=n.node_type, **n.properties)

    def upsert_edges(self, edges: Iterable[KGEdge]) -> None:
        for e in edges:
            self.graph.add_edge(
                e.source,
                e.target,
                key=e.relation,
                relation=e.relation,
                confidence=e.confidence,
                provenance=e.provenance,
                features=asdict(e.features) if e.features else {},
            )


class Neo4jKG:
    def __init__(self, uri: str, user: str, password: str):
        from neo4j import GraphDatabase

        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self.driver.close()

    def init_schema(self) -> None:
        stmts = [
            "CREATE CONSTRAINT node_id_unique IF NOT EXISTS FOR (n:Entity) REQUIRE n.node_id IS UNIQUE",
            "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (n:Entity) ON (n.node_type)",
        ]
        with self.driver.session() as session:
            for s in stmts:
                session.run(s)

    def upsert_nodes(self, nodes: Iterable[KGNode]) -> None:
        q = """
        MERGE (n:Entity {node_id: $node_id})
        SET n.label = $label, n.node_type = $node_type, n += $props
        """
        with self.driver.session() as session:
            for n in nodes:
                session.run(q, node_id=n.node_id, label=n.label, node_type=n.node_type, props=n.properties)

    def upsert_edges(self, edges: Iterable[KGEdge]) -> None:
        q = """
        MATCH (a:Entity {node_id:$src}), (b:Entity {node_id:$dst})
        MERGE (a)-[r:REL {relation:$rel}]->(b)
        SET r.confidence=$conf, r.provenance=$prov, r.features=$features
        """
        with self.driver.session() as session:
            for e in edges:
                session.run(
                    q,
                    src=e.source,
                    dst=e.target,
                    rel=e.relation,
                    conf=e.confidence,
                    prov=e.provenance,
                    features=asdict(e.features) if e.features else {},
                )
