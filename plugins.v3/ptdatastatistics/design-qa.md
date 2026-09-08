# PTDataStatistics 养老进度页 Design QA

- Source visual truth: `C:\Users\cz\.codex\generated_images\01a06dde-3ead-78b0-9af3-51dd41fad0fd\exec-9016ecdb-1a86-4c03-b6be-1910273d49c5.png`
- Implementation: 本地 Vite 预览，使用 Codex In-app Browser 校验。
- Viewport: 1264 × 720 CSS px，深色主题，养老进度标签激活。
- State: 7 个已加入十二大站点、5 个未加入节点；观众站选中并展示完整等级路线。

## Visual findings

- 无 P0/P1/P2 遗留问题。
- 十二大进度采用单条横向里程碑；已加入节点显示编号、站点图标、名称和加入日期，未加入节点仅显示编号与锁定状态，不泄露站点名称。
- 汇总数据固定在标题右侧，最新加入站点有独立标记，底部保留“还差 5 个站点”。
- 已加入站点按 MoviePilot 保存的完整加入时间排序；同一天加入时继续按时分秒判断真实先后。
- 页面沿用现有 MoviePilot/Vuetify 深色主题、圆角、字体和语义色，不引入新的设计语言。

## Layout and scroll checks

- `.retirement-detail`：`clientHeight = 1308px`，`scrollHeight = 1308px`，`overflow-y = visible`。
- `.retirement-explorer`：`clientHeight = 1308px`，`scrollHeight = 1308px`，`overflow-y = visible`。
- 右侧站点明细没有内部纵向滚动条，下一等级、保号目标和完整等级路线全部撑开，由外层页面统一滚动。
- 左侧站点列表继续保持独立滚动和桌面端粘性定位；移动端自动回到普通文档流。

## Interaction checks

- [x] 养老进度标签可正常激活。
- [x] 十二大已加入与未加入状态区分清晰。
- [x] 未加入节点不显示站点名称。
- [x] 右侧下一等级、保号目标和等级路线完整展开。
- [x] 等级行展开/折叠能力保持不变。
- [x] 左侧站点选择逻辑保持不变。

final result: passed
