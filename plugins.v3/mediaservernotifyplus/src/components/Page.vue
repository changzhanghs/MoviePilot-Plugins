<script setup>
defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'MediaServerNotifyPlus' },
})
defineEmits(['action', 'switch', 'close'])
</script>

<template>
  <VCard rounded="xl" variant="outlined">
    <VCardTitle class="d-flex align-center ga-3 pa-5">
      <VAvatar color="primary" variant="tonal"><VIcon icon="mdi-bell-ring-outline" /></VAvatar>
      <div><div>媒体库通知</div><div class="text-caption text-medium-emphasis">通知样式请在插件配置中管理</div></div>
      <VBtn class="ml-auto" icon="mdi-close" variant="text" @click="$emit('close')" />
    </VCardTitle>
    <VDivider />
    <VCardText class="pa-5">每种媒体事件都能独立选择字段、调整顺序和修改展示名称。</VCardText>
  </VCard>
</template>
