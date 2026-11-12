import pytest
from glycopath_research.structure_graph import parse_glycan,compare_supported_graphs,ParseError

def test_lewis_structure_conflict():
    a=parse_glycan('Gal(b1-4)[Fuc(a1-3)]GlcNAc')
    b=parse_glycan('Gal(b1-3)[Fuc(a1-4)]GlcNAc')
    assert compare_supported_graphs(a,b)=='DIFFERENT_SUPPORTED_GRAPH'

def test_branch_order_invariant():
    a=parse_glycan('Gal(b1-4)[Fuc(a1-3)]GlcNAc')
    b=parse_glycan('Fuc(a1-3)[Gal(b1-4)]GlcNAc')
    assert compare_supported_graphs(a,b)=='SAME_SUPPORTED_GRAPH'

def test_partial_is_not_full_identity():
    a=parse_glycan('Gal(?1-4)GlcNAc')
    b=parse_glycan('Gal(b1-4)GlcNAc')
    assert compare_supported_graphs(a,b)=='UNRESOLVED'

def test_multibranch():
    assert len(parse_glycan('Neu5Ac(a2-3)Gal(b1-4)[Fuc(a1-3)]GlcNAc').edges)==3

def test_reject_unsupported():
    with pytest.raises(ParseError):parse_glycan('Gal[bad](b1-4)GlcNAc')
    with pytest.raises(ParseError):parse_glycan('Gal(b1-4)[Fuc(a1-3)GlcNAc')
    with pytest.raises(ParseError):parse_glycan('Gal(b1-4)GlcNAc(b1-3)')
