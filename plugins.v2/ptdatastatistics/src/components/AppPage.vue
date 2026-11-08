<script setup>
import PTStatsWorkbench from './PTStatsWorkbench.vue'

defineProps({
  api: { type: Object, default: () => ({}) },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'PTDataStatistics' },
  sourcePluginId: { type: String, default: '' },
  nativeSubscribe: { type: Function, default: null },
})

defineEmits(['action'])
</script>

<template>
  <PTStatsWorkbench :api="api" :plugin-id="pluginId" @action="$emit('action')" />
</template>

<style scoped>
/* MoviePilot 的空页脚默认占 8rem，仅在本插件独立页面收起空占位。 */
:global(.layout-content-wrapper:has(.plugin-app-page .pt-workbench) > .layout-footer > .footer-content-container:empty) {
  block-size: 0;
}
/* 外层底部 4px 加工作台自身 4px，与 MP 导航栏底部 8px 对齐。 */
:global(.layout-page-content:has(.plugin-app-page .pt-workbench)) {
  padding-block-end: 4px;
}
</style>
