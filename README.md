# pairwise-occlusion-cull

大场景快速转视角时，山体和城墙突然消失又出现：Hi-Z 用上一帧深度生成，相机切换没清；反向 Z 的 mip 比较方向写反；实例包围盒没算骨骼和粒子扩张；两阶段遮挡把保守深度当精确；地形分块与静态合批的 bounds 没合并；门户连通的物体被单独剔除；遮挡回读延迟导致抖动；远处 mip 选择过激；相机近平面变化后投射矩阵没更新；多视图分屏共用一张 Hi-Z。render/occlusion_cull.py 是核心，tests/test_occlusion_cull.py 15个红。要修的是：深度重建与清历史；反向 Z 比较；动态 bounds 扩张；保守两阶段；分块 bounds 合并；门户连通组剔除；延迟回读校验；mip 选择加滞后；近平面矩阵同步；分屏独立 Hi-Z。

## 运行

```bash
python -m pytest tests -q
```

初始状态：15 个用例失败。修复实现使全部用例通过，不要修改 `tests/` 下的测试。

子方向：图形渲染；任务类型：Bugfix；语言/框架：Python 3, pytest；环境可复现等级：无外部依赖。
