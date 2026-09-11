# PTDataStatistics 等级进度 Design QA

- Source visual truth: `C:\Users\cz\Pictures\Saved Pictures\Codex 图像 2026年9月11日 08_38_58.png`
- Implementation: 本地 Vite 预览，使用实际 `PTStatsWorkbench.vue`、Vuetify 深色主题和模拟站点数据。
- Desktop state: 当前 `User`、下一等级 `Power User`、保号目标 `Extreme User`，共 7 个可见等级节点。

## Visual comparison

- 顶部路线从当前等级开始，使用编号圆形节点、分段连线、状态徽标和预计日期；文字位于连线下方，不再与连线重叠。
- “下一等级”区域使用单张宽卡片：标题和预计日期在顶部，左侧显示总体进度，右侧按“目标要求、当前进度、剩余、时间、完成进度”展示要求明细；时间仅使用已有的注册达标日与做种积分预计日期。
- 右上角整体预计达成时间取所有未完成要求中已有预计日期的最晚值，与表格各项时间保持一致。
- 所有站点的等级明细都将“未达成”信息固定在右侧对齐；长内容换行后仍保持右对齐且不溢出。
- 注册时间位于做种积分下方，未合格时的当前进度使用实际累计天数，合格后仅显示“达成”；PTD 最新记录缺少做种积分时速时，回退使用该站最近一个有效时速。
- 左侧站点进度不仅计入已完整达成的等级段，也按比例计入当前正在升级一段的要求完成度。
- “等级路线与要求”改为真正的表格结构，列宽、行高和当前/下一等级高亮与参考图保持同一信息层级。
- 保留项目既有的 MoviePilot/Vuetify 深色主题、颜色变量和圆角体系，没有引入与现有页面冲突的新设计语言。
- 站点等级与数值继续来自原数据结构；视觉调整没有改变同步、计算或展开交互。

## Functional and responsive checks

- [x] 当前、下一等级、普通待达成和保号目标状态均有独立视觉状态。
- [x] 顶部每个节点只展示一次预计信息，不再出现重复的“待同步积分时速”。
- [x] 下一等级要求使用“剩余”，未恢复旧的“还差”措辞。
- [x] 当前等级与下一等级说明默认展开，其余等级仍可点击展开。
- [x] 960px 以下总体进度改为上下布局；表格保留横向浏览，避免压缩成不可读列。
- [x] 720px 以下标题与预计时间纵向排列，要求表和路线表保持完整列结构。

## Verification

- Browser-rendered desktop comparison completed against the supplied reference.
- Frontend production build completed successfully.
- Python contract suite: 62 tests passed.
- `git diff --check`: passed.

## 2026-09-12 完整等级路线复核

- Source visual truth: `C:\Users\cz\AppData\Local\Temp\codex-clipboard-f65e13e4-26d5-451f-bfbe-219c7d1e9a92.png`（1544 × 1151）。
- Implementation capture: Codex 内置浏览器中的本地 QA 页面 `http://127.0.0.1:4173/qa.html`（会话截图，1544 × 1000 CSS px，未持久化为仓库文件）。
- Test state: 红豆饭，当前 `Power User`，下一等级 `Elite User`，保号目标 `Extreme User`；完整路线还包含目标后的 `Ultimate User` 与 `Nexus Master`。

### Full-view and focused comparison

- 顶部养老路线现从首级开始显示：`Peasant`、`User` 等已到达等级不会再因当前等级过滤而消失，并继续显示到保号目标 `Extreme User`。
- 顶部进度线把当前等级之前的完整区段计入进度，再叠加下一等级要求的当前完成比例；编号、状态色、间距、文字层级和既有暗色主题保持不变。
- 底部“等级路线与要求”改用站点完整 `route`，QA 中确认从 `Peasant` 一直列到 `Nexus Master`，不再被保号目标截断。
- 当前等级与下一等级仍默认展开，普通已到达、待达成及保号目标的状态样式和展开交互均保留。
- 聚焦检查未发现文字重叠、水平溢出、错位或颜色回归；字体、间距、色彩、图标资源和中文文案与原组件一致。

### Iteration history and checks

- Initial implementation issue: 顶部通过 `route.slice(currentIndex)` 隐藏已到达等级，底部又复用了截断到保号目标的路线。
- Fix: 顶部使用完整养老路线，底部独立使用站点完整等级列表，同时修正顶部路线总进度基准。
- Post-fix evidence: 浏览器可访问性树确认顶部包含当前等级前的节点，底部包含保号目标后的 `Ultimate User`、`Nexus Master`；浏览器控制台无 warning/error。
- Automated verification: 插件 45 项测试、宿主契约 21 项测试、Vite production build 和 `git diff --check` 全部通过。
- Findings: 无 P0、P1 或 P2 缺陷。

final result: passed
