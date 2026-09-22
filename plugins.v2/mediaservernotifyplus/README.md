# 媒体库通知

面向 MoviePilot V2/V3 的 Emby、Jellyfin、Plex 媒体服务器通知插件。

## 版本

- MoviePilot V2：`2.0.5`
- MoviePilot V3：`3.0.5`
- 插件 ID：`MediaServerNotifyPlus`
- MoviePilot 通知类型固定为“媒体库”，消息渠道遵循 MoviePilot 全局设置。

## 配置界面

通知类型使用独立卡片展示。每张卡片可以启用或停用，点击后打开字段配置弹窗：

- 展示当前事件真实可能取得的全部字段；
- 勾选需要展示的字段；
- 拖动调整字段顺序，触摸设备也可以使用上下移动按钮；
- 只允许修改字段展示名称，例如 `IP` 改为 `IP地址`；
- 字段没有真实值时自动隐藏整行。

右上角“设置”包含插件开关、媒体服务器选择、剧集入库聚合、去重及测试通知等全局选项。元数据按已勾选字段自动补查，IP 归属地作为每种通知的独立可选字段。

## 通知结构

事件标题和媒体名称为固定头部，不参与字段排序。例如：

```text
📂 已入库 1 个文件
兰香如故 (2026)

📺 季集：S01E21
📁 分类：国产剧集
⭐ 评分：6.8/10
```

成功解析 TMDB ID 时，整张通知卡片跳转对应的 TMDB 电影或电视剧页面，不再单独展示 TMDB ID 和 TMDB 链接。

## 媒体服务器筛选

配置页读取 MoviePilot 中已启用的媒体服务器，可选择需要接收通知的 Emby、Jellyfin 或 Plex 实例。

## V2/V3 适配

- V2 使用 `NotificationType.MediaServer`、兼容 `tmdb_id` 以及 V2 媒体服务器帮助类。
- V3 使用公开 SDK、`MessageType.MediaServer` 以及 `media_source + media_id` 统一媒体身份。
- 两版共用通知字段、去重、聚合和媒体库筛选逻辑，并分别发布各自的 Vue 联邦配置界面。
