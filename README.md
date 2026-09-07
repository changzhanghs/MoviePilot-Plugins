# MoviePilot V3 · PT数据统计

`PTDataStatistics` `v1.0.0` 是一个仅面向 MoviePilot V3（`>= 3.0.0`）的站点账户数据统计插件。源码位于 `plugins.v3/ptdatastatistics`。

插件不会直接访问 PT 站点，也不会读取下载器；它在 MoviePilot 完成站点数据刷新后，将 MP 已有的账户快照复制到独立插件数据库，用于历史保留和统计展示。

安装时将插件目录、`package.v3.json` 条目和 `icons/ptdatastatistics.svg` 按 MoviePilot 插件仓库结构发布。前端 `dist` 已由 Vue 模块联邦构建，安装后无需在 MoviePilot 容器内执行 Node.js 构建。

本仓库直接从 `main` 分支分发插件源码和已构建前端，不依赖额外的 GitHub Release 压缩包。

## 安装

将以下仓库地址加入 MoviePilot 的 `PLUGIN_MARKET`，刷新插件市场后搜索“PT数据统计”：

```text
https://github.com/changzhanghs/MoviePilot-Plugins
```
