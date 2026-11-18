"""第 51 批：大场景快速转视角时，山体和城墙突然消失又出现。

修复清单：
1. 深度重建与清历史：相机切换（view/proj 突变）时作废上一帧 Hi-Z，重新生成。
2. 反向 Z 比较：mip_compare 支持 reverse_z，比较方向随之翻转。
3. 动态 bounds 扩张：expand_bounds 按骨骼/粒子余量外扩 AABB。
4. 保守两阶段：two_phase_cull 区分保守深度与精确深度，保守结果只做预剔除。
5. 分块 bounds 合并：merge_bounds 合并地形分块与静态合批的 AABB。
6. 门户连通组剔除：portal_connected 按门户图做连通判断，连通组整体剔除/保留。
7. 延迟回读校验：readback_valid 丢弃超过延迟窗口的遮挡回读结果，避免抖动。
8. mip 选择加滞后：select_mip 支持 previous/hysteresis，避免远处层级来回跳。
9. 近平面矩阵同步：projection_stale 检测 near 等参数变化，触发投影矩阵重建。
10. 分屏独立 Hi-Z：HizPool 按视图 id 各持一张 Hi-Z，不再共用。
"""

import math

# ---------------------------------------------------------------------------
# 1. 深度重建与清历史
# ---------------------------------------------------------------------------


def should_reset_hiz(prev_view_proj, curr_view_proj, tol=1e-4):
    """相机切换/大幅移动时，上一帧深度生成的 Hi-Z 必须作废重建。

    比较前后两帧的 view-proj 矩阵（扁平序列），任一元素差异超过 tol
    即视为相机切换，返回 True（需要清空历史重新生成 Hi-Z）。
    """
    if prev_view_proj is None or curr_view_proj is None:
        return True
    if len(prev_view_proj) != len(curr_view_proj):
        return True
    return any(abs(p - c) > tol for p, c in zip(prev_view_proj, curr_view_proj))


# ---------------------------------------------------------------------------
# Hi-Z 构建（min-pooling；reverse-Z 管线传 reduce=max）
# ---------------------------------------------------------------------------


def build_hiz(level0, reduce=min):
    """从深度数组构建逐级递减的 Hi-Z 金字塔。

    返回 [level0, level1, ..., levelN]，levelN 只剩 1 个 texel。
    默认 min-pooling（常规深度，越远值越大，取最近遮挡）；
    反向 Z 管线应传 reduce=max。
    """
    levels = [list(level0)]
    while len(levels[-1]) > 1:
        cur = levels[-1]
        nxt = []
        for i in range(0, len(cur) - 1, 2):
            nxt.append(reduce(cur[i], cur[i + 1]))
        if len(cur) % 2 == 1:  # 奇数尾部直接带上，不丢样本
            nxt.append(cur[-1])
        levels.append(nxt)
    return levels


# ---------------------------------------------------------------------------
# 2. 反向 Z 的 mip 比较
# ---------------------------------------------------------------------------


def mip_compare(sample_depth, occluder_depth, reverse_z=False):
    """判断采样点是否被遮挡。

    常规深度（近小远大）：sample > occluder 即被挡。
    反向 Z（近大远小）：比较方向翻转，sample < occluder 即被挡。
    相等不算遮挡（同一表面）。
    """
    if reverse_z:
        return bool(sample_depth < occluder_depth)
    return bool(sample_depth > occluder_depth)


# ---------------------------------------------------------------------------
# 3. 动态 bounds 扩张（骨骼/粒子余量）
# ---------------------------------------------------------------------------


def expand_bounds(bounds, margin):
    """按动态余量扩张 AABB，支持 2D(4 元) / 3D(6 元)。

    骨骼动画、粒子系统的最大偏移必须计入 margin，
    否则包围盒偏小会被误剔除。
    """
    half = len(bounds) // 2
    mins = tuple(v - margin for v in bounds[:half])
    maxs = tuple(v + margin for v in bounds[half:])
    return mins + maxs


# ---------------------------------------------------------------------------
# 4. 保守两阶段遮挡
# ---------------------------------------------------------------------------


def two_phase_cull(conservative_occluded, exact_occluded=None):
    """两阶段遮挡：保守深度只用于预剔除，精确结果未回读前不得当最终结论。

    第一阶段（保守深度）判定被挡 -> 返回 'pending'，需等第二阶段精确
    回读确认；精确结果可用时以精确结果为准（True/False）。
    """
    if exact_occluded is not None:
        return bool(exact_occluded)
    if conservative_occluded:
        return "pending"
    return False


# ---------------------------------------------------------------------------
# 5. 分块 bounds 合并
# ---------------------------------------------------------------------------


def merge_bounds(a, b):
    """合并两个 AABB（地形分块与静态合批共用同一包围盒参与剔除）。"""
    half = len(a) // 2
    mins = tuple(min(x, y) for x, y in zip(a[:half], b[:half]))
    maxs = tuple(max(x, y) for x, y in zip(a[half:], b[half:]))
    return mins + maxs


# ---------------------------------------------------------------------------
# 6. 门户连通组剔除
# ---------------------------------------------------------------------------


def portal_connected(source, target, graph):
    """判断两个分块是否通过门户连通（BFS）。

    连通的物体必须作为一组整体剔除/保留，不能单独剔除。
    """
    if source == target:
        return True
    visited = {source}
    stack = [source]
    while stack:
        node = stack.pop()
        for nxt in graph.get(node, ()):
            if nxt == target:
                return True
            if nxt not in visited:
                visited.add(nxt)
                stack.append(nxt)
    return False


# ---------------------------------------------------------------------------
# 7. 延迟回读校验
# ---------------------------------------------------------------------------


def readback_valid(result_frame, current_frame, max_latency=2):
    """遮挡回读结果只在延迟窗口内有效，过期结果丢弃（避免可见性抖动）。"""
    return 0 <= (current_frame - result_frame) <= max_latency


# ---------------------------------------------------------------------------
# 8. mip 选择（加滞后，避免远处层级来回跳）
# ---------------------------------------------------------------------------


def select_mip(screen_area, total_pixels, previous=None, hysteresis=1):
    """按屏幕占比选择 Hi-Z mip 层级：占比越大选越粗的层级。

    传入 previous（上一帧层级）时启用滞后：新旧层级差不超过
    hysteresis 则维持旧层级，防止远处物体 mip 选择过激导致闪烁。
    """
    if screen_area <= 0 or total_pixels <= 0:
        mip = 0
    else:
        side = math.sqrt(screen_area)
        mip = max(0, int(math.ceil(math.log2(side / 8.0))) if side > 0 else 0)
    if previous is not None and abs(mip - previous) <= hysteresis:
        return previous
    return mip


# ---------------------------------------------------------------------------
# 9. 近平面变化后投影矩阵同步
# ---------------------------------------------------------------------------


def projection_stale(cached_params, near, far, fov, aspect, tol=1e-6):
    """近平面（或 far/fov/aspect）变化后，缓存的投影矩阵必须重建。"""
    if cached_params is None:
        return True
    keys = ("near", "far", "fov", "aspect")
    curr = dict(zip(keys, (near, far, fov, aspect)))
    return any(abs(cached_params.get(k, float("nan")) - curr[k]) > tol for k in keys)


# ---------------------------------------------------------------------------
# 10. 分屏独立 Hi-Z
# ---------------------------------------------------------------------------


class HizPool:
    """多视图分屏：每个视图 id 各持一张独立 Hi-Z，绝不共用。"""

    def __init__(self):
        self._pyramids = {}

    def update(self, view_id, level0, reduce=min):
        self._pyramids[view_id] = build_hiz(level0, reduce=reduce)
        return self._pyramids[view_id]

    def get(self, view_id):
        return self._pyramids.get(view_id)

    def invalidate(self, view_id):
        """相机切换时只清对应视图的历史。"""
        self._pyramids.pop(view_id, None)
