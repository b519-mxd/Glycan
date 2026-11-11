from glycopath_research.public_benchmarks import features
def test_chemical_position_features():
    assert features('A','Gal(b1-3)GlcNAc','glycan_only')!=features('A','Gal(b1-4)GlcNAc','glycan_only')
def test_context_features():
    assert features('A','Gal(b1-3)GlcNAc','combined')!=features('B','Gal(b1-3)GlcNAc','combined')
