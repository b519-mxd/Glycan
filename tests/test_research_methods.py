from glycopath_research.morphology import (parse_single_linkage, compare_structures,
        Identity, align_candidates, GlycanDescription)
from glycopath_research.evidence import Claim, fuse_claims, audit_path

def test_conflicting_linkages_are_not_same():
    x=parse_single_linkage("Neu5Ac(a2-3)Gal")
    y=parse_single_linkage("Neu5Ac(a2-6)Gal")
    assert compare_structures(x,y)==Identity.CONFLICT
    unknown=parse_single_linkage("Neu5Ac(?2-?)Gal")
    assert compare_structures(x,unknown)==Identity.COMPATIBLE_NOT_IDENTICAL
    assert align_candidates(unknown,{"s3":x,"s6":y})["linked_id"] is None

def test_registry_exact():
    x=GlycanDescription("g",("Gal","GlcNAc"),complete=True)
    y=GlycanDescription("n",("Gal","GlcNAc"),complete=True)
    assert compare_structures(x,y)==Identity.EXACT

def test_repeated_source_not_independent():
    a=Claim("g","binds","r","d1","e1",1,{"cell":"CHO"},"x",0.8)
    b=Claim("g","binds","r","d2","e2",1,{"cell":"CHO"},"x",0.8)
    x=fuse_claims([a,b])[0]
    assert x["mention_count"]==2 and x["independent_source_groups"]==1 and x["support_index"]==1

def test_conflict_in_different_contexts_not_pooled():
    a=Claim("g","binds","r","d1","e1",1,{"cell":"A"})
    b=Claim("g","binds","r","d2","e2",-1,{"cell":"B"})
    assert len(fuse_claims([a,b]))==2

def test_same_context_opposition_retained():
    a=Claim("g","binds","r","d1","e1",1,{"cell":"A"})
    b=Claim("g","binds","r","d2","e2",-1,{"cell":"A"})
    x=fuse_claims([a,b])[0]
    assert x["has_opposing_reports"] and x["support_index"]==0

def test_path_evidence_and_context_gates():
    a={"provenance":["e1"],"evidence_status":"OBSERVED","context":{"species":"mouse"}}
    b={"provenance":[],"evidence_status":"PREDICTED","context":{"species":"human"}}
    z={p["type"] for p in audit_path([a,b])["issues"]}
    assert {"MISSING_PROVENANCE","NOT_EXPERIMENTAL_OBSERVATION","CONTEXT_MISMATCH"} <= z
