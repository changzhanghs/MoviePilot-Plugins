# MoviePilot-Plugins

1. PT数据统计
2. 媒体库通知

- MoviePilot：`>=2.12.0`（V2 与 V3 共用同一实现和版本）

V3 通过 MoviePilot 官方提供的 V2 插件向后兼容机制加载 `plugins.v2`。

“媒体库通知”提供独立的 V2 `2.0.4` 与 V3 `3.0.4` 实现，支持 Emby、Jellyfin、Plex。配置页按通知类型展示卡片，可分别启停、选择字段、拖动排序并修改字段展示名称；消息渠道遵循 MoviePilot 全局设置，通知类型固定为“媒体库”。

## 安装

将仓库地址加入 MoviePilot 的插件市场设置，刷新插件市场后可搜索“PT数据统计”或“媒体库通知”：

```text
https://github.com/changzhanghs/MoviePilot-Plugins
```
