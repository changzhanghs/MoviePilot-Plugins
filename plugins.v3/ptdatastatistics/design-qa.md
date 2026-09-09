# PTDataStatistics 十二大进度 Design QA

- Source visual truth: `C:\Users\cz\AppData\Local\Temp\codex-clipboard-fab20a5e-bb34-4a92-9a9b-1b80d014bdb9.png`
- Implementation: 本地 Vite 预览，使用 Codex In-app Browser 校验。
- Viewport: 1280 × 720 CSS px，深色主题，养老进度标签激活。
- State: 4 个已加入十二大站点、8 个未加入节点；下方养老进度功能保持原样。

## Visual findings

- 无 P0/P1/P2 遗留问题。
- 十二大进度采用更紧凑的单条横向里程碑；卡片实测高度约 `241px`，比原布局明显收窄。
- 已加入节点只显示编号、站点图标和名称；站点下方不再显示加入日期。
- 已移除“最近加入”标记，汇总数据仍固定在标题右侧，底部继续显示剩余站点数量。
- 未加入节点只显示编号与锁定状态，不泄露站点名称。
- 已加入站点按 MoviePilot 保存的完整加入时间排序；同一天加入时继续按时分秒判断真实先后。
- 页面沿用现有 MoviePilot/Vuetify 深色主题、圆角、字体和语义色，不引入新的设计语言。

## DOM and layout checks

- `.twelve-panel`：`height ≈ 241px`，`width ≈ 1257px`。
- `.twelve-node__latest`：`0` 个。
- `.twelve-node__date`：`0` 个。
- 页面文本不包含“最近加入”；可见站点名称仅为已加入站点。

## Interaction checks

- [x] 养老进度标签可正常激活。
- [x] 十二大已加入与未加入状态区分清晰。
- [x] 未加入节点不显示站点名称。
- [x] 已加入站点下方不显示加入时间。
- [x] “最近加入”标记不再渲染。
- [x] 原有排序、进度统计和下方养老进度交互保持不变。

final result: passed
