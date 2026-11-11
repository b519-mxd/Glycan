"""Conservative glycan partial-linkage matching (NOT a full IUPAC parser)."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import re

class Identity(str, Enum):
    EXACT = "EXACT"
    COMPATIBLE_NOT_IDENTICAL = "COMPATIBLE_NOT_IDENTICAL"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True)
class Linkage:
    donor: str
    acceptor: str
    anomer: str | None = None
    donor_position: int | None = None
    acceptor_position: int | None = None

@dataclass(frozen=True)
class GlycanDescription:
    text: str
    residues: tuple[str, ...] = ()
    linkages: tuple[Linkage, ...] = ()
    complete: bool = False
    registry_id: str | None = None

def parse_single_linkage(text: str) -> GlycanDescription:
    """A(a1-3)B two-residue fragment: no implicit structural completion."""
    pat = r"^([A-Za-z][A-Za-z0-9]*)(?:\(([abαβ?])?([0-9?]+)-([0-9?]+)\))([A-Za-z][A-Za-z0-9]*)$"
    m = re.fullmatch(pat, text.replace(" ", ""))
    if not m:
        return GlycanDescription(text=text)
    left, ano, dp, ap, right = m.groups()
    ano = {"α": "a", "β": "b", "?": None}.get(ano, ano)
    link = Linkage(left, right, ano, int(dp) if dp.isdigit() else None, int(ap) if ap.isdigit() else None)
    return GlycanDescription(text, (left, right), (link,), False)

def compare_structures(a: GlycanDescription, b: GlycanDescription) -> Identity:
    if a.registry_id and a.registry_id == b.registry_id:
        return Identity.EXACT
    if not a.residues or not b.residues:
        return Identity.UNKNOWN
    if a.complete and b.complete and sorted(a.residues) != sorted(b.residues):
        return Identity.CONFLICT
    for x in a.linkages:
        for y in b.linkages:
            if (x.donor, x.acceptor) != (y.donor, y.acceptor):
                continue
            for prop in ("anomer", "donor_position", "acceptor_position"):
                vx, vy = getattr(x, prop), getattr(y, prop)
                if vx is not None and vy is not None and vx != vy:
                    return Identity.CONFLICT
    if a.complete and b.complete and a.residues == b.residues and a.linkages == b.linkages:
        return Identity.EXACT
    if set(a.residues).issubset(set(b.residues)) or set(b.residues).issubset(set(a.residues)):
        return Identity.COMPATIBLE_NOT_IDENTICAL
    return Identity.UNKNOWN

def align_candidates(mention: GlycanDescription, registry: dict[str, GlycanDescription]) -> dict:
    decisions = {k: compare_structures(mention, v).value for k, v in registry.items()}
    exact = [k for k, state in decisions.items() if state == Identity.EXACT.value]
    return {"linked_id": exact[0] if len(exact) == 1 else None,
            "review_required": len(exact) != 1, "candidate_decisions": decisions}
