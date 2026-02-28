from __future__ import annotations

from dataclasses import asdict

from reasoning.path_reasoner import SimplifiedIRRL, best_first_paths


def query_reasoning(graph, query: str, top_k: int, cfg: dict) -> list[dict]:
    q = query.lower()
    start = "glycan:l-type_monosaccharide" if "l" in q else "glycan:d-type_monosaccharide"
    if "vs" in q:
        starts = ["glycan:l-type_monosaccharide", "glycan:d-type_monosaccharide"]
    else:
        starts = [start]
    target = ["phenotype:immune_regulation", "phenotype:anti-inflammatory"]

    irrl = SimplifiedIRRL(graph, lr=cfg["reasoning"]["irrl_lr"])
    for s in starts:
        if s in graph:
            irrl.train(s, target_keywords=target, episodes=cfg["reasoning"]["irrl_episodes"])

    all_paths = []
    for s in starts:
        if s not in graph:
            continue
        paths = best_first_paths(
            graph,
            s,
            target_keywords=target,
            top_k=top_k,
            max_hops=cfg["reasoning"]["max_hops"],
            beam_width=cfg["reasoning"]["beam_width"],
            penalties={"hub_penalty": cfg["reasoning"]["hub_penalty"], "cycle_penalty": cfg["reasoning"]["cycle_penalty"]},
        )
        all_paths.extend(paths)
    all_paths.sort(key=lambda p: p.total_score, reverse=True)
    return [asdict(p) for p in all_paths[:top_k]]
