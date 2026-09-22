<script setup>
import { computed, onMounted, ref } from 'vue'
import { actionMetaFallback, actionOrder, normalizeNotificationModel } from '../notificationModel.js'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'MediaServerNotifyPlus' },
})
const emit = defineEmits(['action', 'switch', 'close'])
const loading = ref(true)
const loadError = ref('')
const model = ref({ types: [] })
const enabledTypes = computed(() => new Set(model.value.types || []))
const targetStorageKey = computed(() => `mediaservernotifyplus:edit:${props.pluginId}`)

function unwrap(value) {
  let current = value
  for (let index = 0; index < 2; index += 1) {
    if (!current || typeof current !== 'object') break
    if (Object.prototype.hasOwnProperty.call(current, 'data')) current = current.data
    else break
  }
  return current
}
function actionLabel(action) {
  return model.value._action_meta?.[action]?.label || actionMetaFallback[action].label
}
function fieldCount(action) {
  return (model.value.field_configs?.[action] || []).filter(row => row.enabled).length
}
async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const response = unwrap(await props.api.get(`plugin/form/${props.pluginId}`, { feedback: 'silent' }))
    model.value = normalizeNotificationModel(response?.model || response || { types: [] })
  } catch (error) {
    loadError.value = error?.message || '读取插件配置失败'
  } finally {
    loading.value = false
  }
}
onMounted(load)

function openConfig(action = '') {
  if (action) {
    try { window.sessionStorage.setItem(targetStorageKey.value, action) } catch (_) { /* ignore */ }
  }
  emit('switch')
}
</script>

<template>
  <VCard class="detail-shell" rounded="xl" variant="flat">
    <VCardTitle class="detail-header">
      <VAvatar color="primary" variant="tonal"><VIcon icon="mdi-bell-ring-outline" /></VAvatar>
      <div><div>媒体库通知</div><div class="text-caption text-medium-emphasis">点击通知类型可进入设置</div></div>
      <VBtn class="ml-auto" prepend-icon="mdi-tune-variant" variant="tonal" @click="openConfig()">设置</VBtn>
      <VBtn icon="mdi-close" variant="text" @click="$emit('close')" />
    </VCardTitle>
    <VDivider />
    <VCardText class="pa-5">
      <div v-if="loading" class="detail-loading"><VProgressCircular indeterminate color="primary" /><span>正在读取通知设置</span></div>
      <VAlert v-else-if="loadError" type="error" variant="tonal">{{ loadError }}</VAlert>
      <div v-else class="detail-grid">
        <VCard
          v-for="action in actionOrder"
          :key="action"
          class="detail-card"
          variant="outlined"
          tabindex="0"
          @click="openConfig(action)"
          @keydown.enter="openConfig(action)"
        >
          <VCardText>
            <div class="detail-card__top"><VIcon :icon="actionMetaFallback[action].icon" color="primary" /><span class="detail-state" :class="{ 'detail-state--off': !enabledTypes.has(action) }" /></div>
            <strong>{{ actionLabel(action) }}</strong>
            <small>{{ enabledTypes.has(action) ? `已启用 · ${fieldCount(action)} 个字段` : '已停用' }}</small>
          </VCardText>
        </VCard>
      </div>
    </VCardText>
  </VCard>
</template>

<style scoped>
.detail-shell { min-width: min(1040px, 92vw); }
.detail-header { display: flex; align-items: center; gap: 12px; padding: 18px 20px; }
.detail-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.detail-card { cursor: pointer; border-radius: 15px; transition: border-color .18s ease, transform .18s ease; }
.detail-card:hover { border-color: rgba(var(--v-theme-primary), .66); transform: translateY(-1px); }
.detail-card .v-card-text { display: grid; gap: 10px; padding: 14px; }
.detail-card__top { display: flex; align-items: center; justify-content: space-between; }
.detail-card strong { font-size: 14px; }
.detail-card small { color: rgba(var(--v-theme-on-surface), .56); }
.detail-state { width: 7px; height: 7px; border-radius: 50%; background: rgb(var(--v-theme-success)); }
.detail-state--off { background: rgba(var(--v-theme-on-surface), .32); }
.detail-loading { display: flex; align-items: center; justify-content: center; gap: 12px; min-height: 260px; color: rgba(var(--v-theme-on-surface), .6); }
@media (max-width: 900px) { .detail-shell { min-width: 0; } .detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) { .detail-grid { grid-template-columns: 1fr; } }
</style>
