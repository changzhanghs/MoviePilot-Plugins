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

final result: passed
