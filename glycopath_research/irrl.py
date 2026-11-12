"""Trainable region-then-entity REINFORCE navigator for a TOY graph.

This is a small engineering prototype, not validated full GlycoPath IRRL.
A real frozen train graph, held-out entity labels and domain-reviewed path gold
are prerequisites for publishable Hits@K and scientific path accuracy.
"""
from __future__ import annotations
from dataclasses import dataclass
import random
import torch
from torch import nn
from torch.distributions import Categorical

@dataclass
class Episode:
    nodes: list[str]
    reached_target: bool
    return_value: float
    policy_log_prob: torch.Tensor

class DualPolicyNavigator(nn.Module):
    def __init__(self, nodes: list[str], regions: dict[str, str], hidden: int = 16):
        super().__init__()
        self.nodes = sorted(nodes)
        self.ids = {n: i for i, n in enumerate(self.nodes)}
        self.regions = regions
        self.region_list = sorted(set(regions.values()))
        self.region_ids = {r: i for i, r in enumerate(self.region_list)}
        self.embedding = nn.Embedding(len(self.nodes), hidden)
        self.region_head = nn.Linear(hidden, len(self.region_list))
        self.entity_head = nn.Linear(hidden, hidden)

    def navigate(self, adjacency: dict[str, list[tuple[str, dict]]], start: str,
                 targets: set[str], max_hops: int = 4, sample: bool = True) -> Episode:
        visited = [start]
        log_prob = torch.tensor(0., dtype=torch.float32)
        for _ in range(max_hops):
            current = visited[-1]
            options = [(n, a) for n, a in adjacency.get(current, [])
                       if n not in visited and a.get("structure_status") != "CONFLICT"
                       and a.get("provenance") and a.get("evidence_status") == "OBSERVED"]
            if not options:
                break
            valid_regions = sorted({self.regions[n] for n, _ in options})
            h = self.embedding(torch.tensor(self.ids[current]))
            logits_raw = self.region_head(h)
            logits = torch.full_like(logits_raw, float("-inf"))
            for region in valid_regions:
                logits[self.region_ids[region]] = logits_raw[self.region_ids[region]]
            dist_r = Categorical(logits=logits)
            action_r = dist_r.sample() if sample else torch.argmax(logits)
            log_prob = log_prob + dist_r.log_prob(action_r)
            region = self.region_list[int(action_r.item())]
            candidate_nodes = [n for n, _ in options if self.regions[n] == region]
            node_logits = torch.stack([
                torch.dot(self.entity_head(h), self.embedding(torch.tensor(self.ids[n])))
                for n in candidate_nodes
            ])
            dist_n = Categorical(logits=node_logits)
            action_n = dist_n.sample() if sample else torch.argmax(node_logits)
            log_prob = log_prob + dist_n.log_prob(action_n)
            visited.append(candidate_nodes[int(action_n.item())])
            if visited[-1] in targets:
                break
        reached = visited[-1] in targets
        reward = (1.0 if reached else -0.2) - 0.02 * (len(visited) - 1)
        return Episode(visited, reached, reward, log_prob)

def train_toy_graph(epochs: int = 90, seed: int = 19) -> dict:
    random.seed(seed)
    torch.manual_seed(seed)
    regions = {"glycan:A": "glycan", "receptor:R": "receptor",
               "pathway:P": "pathway", "phenotype:F": "phenotype", "noise:N": "noise"}
    observed = {"provenance": ["toy:ev:1"], "evidence_status": "OBSERVED"}
    graph = {"glycan:A": [("receptor:R", observed), ("noise:N", observed)],
             "receptor:R": [("pathway:P", observed)],
             "pathway:P": [("phenotype:F", observed)], "noise:N": [], "phenotype:F": []}
    policy = DualPolicyNavigator(list(regions), regions)
    optimizer = torch.optim.Adam(policy.parameters(), lr=0.02)
    trace = []
    for epoch in range(epochs):
        ep = policy.navigate(graph, "glycan:A", {"phenotype:F"}, sample=True)
        optimizer.zero_grad()
        loss = -ep.policy_log_prob * ep.return_value
        loss.backward()
        optimizer.step()
        trace.append({"epoch": epoch, "reward": ep.return_value,
                      "success": ep.reached_target, "path": ep.nodes})
    test = policy.navigate(graph, "glycan:A", {"phenotype:F"}, sample=False)
    return {"task_type": "TOY_SMOKE_NOT_SCIENTIFIC", "epochs": epochs,
            "training_success_count": sum(e["success"] for e in trace),
            "greedy_final_path": test.nodes, "greedy_reached_target": test.reached_target,
            "trace": trace}
