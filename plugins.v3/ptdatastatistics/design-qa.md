# PTDataStatistics 历史数据页 Design QA

- Source visual truth: `C:\Users\cz\.codex\generated_images\01a06dde-3ead-78b0-9af3-51dd41fad0fd\exec-7319e535-24fd-48dd-bdbd-2f04a1d0a4dc.png`
- Implementation: 本地 Vite 预览 `http://127.0.0.1:4174/`，使用 Codex In-app Browser 校验。
- Viewport: 1280 × 720 CSS px，device scale factor 1。
- State: 深色主题，历史数据标签激活，31 天、7 个模拟站点；验证日、周和单站点筛选状态。

## Findings

- 无 P0/P1/P2 遗留问题。
- 历史导航固定为 190px 窄侧栏，右侧内容宽 1065px；周期和站点明细均保持独立滚动。
- 站点表格容器 `clientWidth` 与 `scrollWidth` 均为 1005px，不存在横向滚动。
- 小时曲线实际尺寸为 1022 × 245px，上传为绿色曲线、下载为红色曲线，曲线清晰且未遮挡标题和图例。
- 页面不再包含“站点贡献”区域。
- 点击“大青虫”行后，图表标题更新为“大青虫 · 每小时流量”，并出现“查看全部站点”操作；再次返回可恢复汇总曲线。
- 切换到“周”后，左侧按周汇总，右侧标题和数据切换为“按日期流量”，不存在小时数据误用。
- 字体、颜色、圆角和语义状态沿用 MoviePilot/Vuetify 主题；站点图标继续由现有 `SiteAvatar` 组件提供。

## Data fidelity

- 日视图小时曲线只使用 MoviePilot 同日原始采样之间的累计差值，不进行平均拆分或虚构小时数据。
- 当同日相邻采样不足时，明确显示“暂无法计算小时增量”。
- 周/月视图基于插件现有日级历史快照聚合，点击站点后仅展示该站点序列。

## Interaction checks

- [x] 日 / 周 / 月周期切换。
- [x] 左侧周期选择联动右侧汇总和图表。
- [x] 点击站点行筛选上方曲线。
- [x] “查看全部站点”恢复汇总曲线。
- [x] 站点贡献已移除。
- [x] 表格无横向滚动。

final result: passed
