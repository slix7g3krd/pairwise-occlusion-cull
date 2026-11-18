import pytest
from render import occlusion_cull as mod

CASES = [
    ("hiz_depth", "len(m.build_hiz([1, 3, 2, 4])) >= 3"),
    ("hiz_min_pool", "m.build_hiz([1, 3, 2, 4])[1][0] == 1"),
    ("mip_occluded", "m.mip_compare(0.8, 0.5) is True"),
    ("mip_visible", "m.mip_compare(0.2, 0.5) is False"),
    ("bounds_expand", "m.expand_bounds((0.0, 0.0, 10.0, 10.0), 2.0) == (-2.0, -2.0, 12.0, 12.0)"),
    ("bounds_merge", "m.merge_bounds((0.0, 0.0, 5.0, 5.0), (3.0, 3.0, 10.0, 10.0)) == (0.0, 0.0, 10.0, 10.0)"),
    ("portal_true", "m.portal_connected('a', 'b', {'a': ['b'], 'b': []}) is True"),
    ("portal_false", "m.portal_connected('a', 'c', {'a': ['b'], 'b': []}) is False"),
    ("mip_small", "m.select_mip(1.0, 1024.0) == 0"),
    ("mip_large", "m.select_mip(1024.0, 1024.0) >= 0"),
    ("mip_monotonic", "m.select_mip(512.0, 1024.0) >= m.select_mip(128.0, 1024.0)"),
    ("hiz_single", "len(m.build_hiz([5])) == 1"),
    ("mip_equal", "m.mip_compare(0.5, 0.5) is False"),
    ("bounds_zero", "m.expand_bounds((0.0, 0.0, 1.0, 1.0), 0.0) == (0.0, 0.0, 1.0, 1.0)"),
    ("bounds_nested", "m.merge_bounds((0.0, 0.0, 10.0, 10.0), (2.0, 2.0, 4.0, 4.0)) == (0.0, 0.0, 10.0, 10.0)")
]

@pytest.mark.parametrize("name,expr", CASES, ids=[c[0] for c in CASES])
def test_contract(name, expr):
    assert eval(expr, {"m": mod, "approx": pytest.approx})
