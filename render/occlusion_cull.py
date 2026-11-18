"""第 51 批：大场景快速转视角时，山体和城墙突然消失又出现：H..."""

def build_hiz(level0):
    """从 2D 深度数组构建逐级最小值 Hi-Z。"""
    raise NotImplementedError("TODO: build_hiz")

def mip_compare(sample_depth, occluder_depth):
    """判断采样点是否被遮挡。"""
    raise NotImplementedError("TODO: mip_compare")

def expand_bounds(bounds, margin):
    """按动态物体余量扩张 AABB。"""
    raise NotImplementedError("TODO: expand_bounds")

def merge_bounds(a, b):
    """合并两个 AABB。"""
    raise NotImplementedError("TODO: merge_bounds")

def portal_connected(source, target, graph):
    """判断两个分块是否通过门户连通。"""
    raise NotImplementedError("TODO: portal_connected")

def select_mip(screen_area, total_pixels):
    """按屏幕占比选择 Hi-Z mip 层级。"""
    raise NotImplementedError("TODO: select_mip")
