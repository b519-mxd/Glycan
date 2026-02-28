from __future__ import annotations

import math
import random
from collections import defaultdict

from common.types import ReasoningPath


def _edge_score(edge_data: dict, degree: int, penalties: dict[str, float]) -> float:
    conf = edge_data.get("confidence", 0.3)
    hub_penalty = penalties["hub_penalty"] * math.log1p(degree)
    return max(0.01, conf - hub_penalty)


def best_first_paths(
    graph,
    start: str,
    target_keywords: list[str],
    top_k: int = 5,
    max_hops: int = 4,
    beam_width: int = 6,
    penalties: dict[str, float] | None = None,
) -> list[ReasoningPath]:
    penalties = penalties or {"hub_penalty": 0.1, "cycle_penalty": 0.2}
    frontier = [([start], [], [], 1.0, [])]
    complete: list[ReasoningPath] = []

    for _ in range(max_hops):
        next_frontier = []
        for nodes, rels, scores, total, ev_chain in frontier:
            cur = nodes[-1]
            for _, nbr, key, data in graph.out_edges(cur, keys=True, data=True):
                if nbr in nodes:
                    new_total = total - penalties["cycle_penalty"]
                else:
                    new_total = total * _edge_score(data, graph.degree(nbr), penalties)
                new_nodes = nodes + [nbr]
                new_rels = rels + [key]
                new_scores = scores + [data.get("confidence", 0.3)]
                new_chain = ev_chain + data.get("provenance", [])
                if any(k.lower() in nbr.lower() for k in target_keywords):
                    complete.append(
                        ReasoningPath(
                            nodes=new_nodes,
                            relations=new_rels,
                            edge_scores=new_scores,
                            total_score=round(new_total, 4),
                            confidence_breakdown={
                                "edge_mean": round(sum(new_scores) / len(new_scores), 3),
                                "path_length": len(new_rels),
                            },
                            evidence_chain=new_chain,
                            explanation=" -> ".join(new_nodes),
                        )
                    )
                next_frontier.append((new_nodes, new_rels, new_scores, new_total, new_chain))
        next_frontier.sort(key=lambda x: x[3], reverse=True)
        frontier = next_frontier[:beam_width]
    complete.sort(key=lambda x: x.total_score, reverse=True)
    return complete[:top_k]


class SimplifiedIRRL:
    def __init__(self, graph, lr: float = 0.02):
        self.graph = graph
        self.lr = lr
        self.coarse_policy = defaultdict(lambda: 0.5)  # community preference
        self.fine_policy = defaultdict(lambda: 0.5)  # edge preference

    def _community(self, node: str) -> str:
        return node.split(":")[0]

    def train(self, start: str, target_keywords: list[str], episodes: int = 50) -> None:
        for _ in range(episodes):
            path = [start]
            reward = 0.0
            for _hop in range(4):
                cur = path[-1]
                out_edges = list(self.graph.out_edges(cur, keys=True, data=True))
                if not out_edges:
                    break
                weighted = []
                for _, nbr, key, data in out_edges:
                    c = self._community(nbr)
                    w = self.coarse_policy[c] * self.fine_policy[(cur, key, nbr)] * data.get("confidence", 0.3)
                    weighted.append((w, nbr, key, data))
                _, nbr, key, data = max(weighted, key=lambda x: x[0]) if random.random() > 0.2 else random.choice(weighted)
                path.append(nbr)
                reward += data.get("confidence", 0.3)
                if any(k.lower() in nbr.lower() for k in target_keywords):
                    reward += 1.0
                    break
            baseline = 0.5
            advantage = reward - baseline
            for i in range(1, len(path)):
                c = self._community(path[i])
                self.coarse_policy[c] += self.lr * advantage
                prev = path[i - 1]
                for _, nb, key, _ in self.graph.out_edges(prev, keys=True, data=True):
                    if nb == path[i]:
                        self.fine_policy[(prev, key, nb)] += self.lr * advantage
