from __future__ import annotations

from collections import defaultdict


class SimpleMultiDiGraph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self._out = defaultdict(list)
        self._in = defaultdict(list)

    def __contains__(self, node: str) -> bool:
        return node in self.nodes

    def add_node(self, node_id: str, **attrs):
        self.nodes.setdefault(node_id, {}).update(attrs)

    def add_edge(self, src: str, dst: str, key: str, **attrs):
        item = (src, dst, key, attrs)
        self._out[src].append(item)
        self._in[dst].append(item)

    def out_edges(self, node: str, keys: bool = True, data: bool = True):
        for src, dst, key, attrs in self._out.get(node, []):
            if keys and data:
                yield (src, dst, key, attrs)
            elif keys:
                yield (src, dst, key)
            else:
                yield (src, dst)

    def degree(self, node: str) -> int:
        return len(self._out.get(node, [])) + len(self._in.get(node, []))
