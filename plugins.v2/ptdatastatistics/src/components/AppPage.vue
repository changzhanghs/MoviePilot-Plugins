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
</style>
