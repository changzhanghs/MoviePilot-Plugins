# 媒体库通知

这是一个面向 MoviePilot V2/V3 的媒体服务器通知插件骨架。通知样式没有固定布局：每种事件都可分别编辑标题与正文。

## 目录

- `plugins.v2/mediaservernotifyplus`：MoviePilot V2 版本
- `plugins.v3/mediaservernotifyplus`：MoviePilot V3 版本
- `package.v2.json` / `package.v3.json`：对应插件市场清单

## 可独立配置的事件

已入库、已删除、开始播放、停止播放、暂停播放、继续播放、登录成功、登录失败、用户标记和系统测试。

每种事件都有自己的：

- 标题模板
- 正文模板（支持多行、Markdown、Emoji 和任意字段顺序）

配置页分为“基础设置”和“通知模板设置”两个独立分类。模板分类中可选择一个事件类型，并打开“保存时发送模板测试”即时查看效果。

## 占位符

`{action}`、`{event}`、`{channel}`、`{server}`、`{title}`、`{item_name}`、`{display_name}`、`{title_link}`、`{media_type}`、`{year}`、`{time}`、`{category}`、`{season_episode}`、`{rating}`、`{region}`、`{status}`、`{genres}`、`{actors}`、`{overview}`、`{user}`、`{device}`、`{client}`、`{ip}`、`{progress}`、`{tmdb_id}`、`{tmdb_url}`、`{media_source}`、`{media_id}`、`{file_count}`、`{album}`、`{artist}`。

含有空占位符的正文行会自动隐藏。例如没有评分时，`⭐ {rating}` 整行不会出现。

如需只在字段有值时显示一段不含占位符的固定文字，可在行首加条件：

```text
[[overview]]━━━━━━━━━━━━━━━━━━
[[overview]]📖 剧情简介
{overview}
```

模板解析器不执行 Python、Jinja 或表达式，只接受上述简单占位符，避免配置内容执行代码。

## V2/V3 适配差异

- V2 使用 `app.core`、`app.helper`、`CategoryHelper` 和兼容的 `tmdb_id`。
- V3 使用 `app.sdk`，通过 `media_source + media_id` 解析媒体身份，并使用宿主分类 SDK。
- 两版共用相同模板、去重、剧集聚合和生命周期逻辑，但各自打包，互不交叉导入。
