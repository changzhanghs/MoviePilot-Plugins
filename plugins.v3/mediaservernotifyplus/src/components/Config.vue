<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { actionMetaFallback, actionOrder, normalizeNotificationModel } from '../notificationModel.js'

const props = defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'MediaServerNotifyPlus' },
  sourcePluginId: { type: String, default: '' },
  nativeSubscribe: { type: Function, default: null },
})
const emit = defineEmits(['layout', 'save', 'close', 'switch'])

const clone = value => JSON.parse(JSON.stringify(value || {}))
const draft = ref(normalizeNotificationModel(props.initialConfig))
const settingsOpen = ref(false)
const editorOpen = ref(false)
const activeAction = ref('library_added')
const draggingIndex = ref(-1)
const saved = ref(false)

watch(() => props.initialConfig, value => { draft.value = normalizeNotificationModel(value) }, { deep: true })
onMounted(() => {
  emit('layout', { maxWidth: '76rem' })
  try {
    const key = `mediaservernotifyplus:edit:${props.pluginId}`
    const requestedAction = window.sessionStorage.getItem(key)
    window.sessionStorage.removeItem(key)
    if (actionOrder.includes(requestedAction)) openEditor(requestedAction)
  } catch (_) { /* sessionStorage 不可用时仍可正常打开配置页 */ }
})

const actionMeta = action => {
  const supplied = draft.value._action_meta?.[action]
  return supplied || actionMetaFallback[action]
}
const fieldMeta = key => draft.value._field_catalog?.[key] || { label: key }
const activeFields = computed(() => draft.value.field_configs?.[activeAction.value] || [])
const activeMeta = computed(() => actionMeta(activeAction.value))
const enabledTypes = computed(() => new Set(draft.value.types || []))
const serverOptions = computed(() => draft.value._server_options || [])

function isEnabled(action) {
  return enabledTypes.value.has(action)
}
function setEnabled(action, enabled) {
  const next = new Set(draft.value.types || [])
  enabled ? next.add(action) : next.delete(action)
  draft.value.types = actionOrder.filter(item => next.has(item))
}
function openEditor(action) {
  activeAction.value = action
  editorOpen.value = true
}
function moveField(from, to) {
  const rows = activeFields.value
  if (from < 0 || to < 0 || from >= rows.length || to >= rows.length || from === to) return
  const [row] = rows.splice(from, 1)
  rows.splice(to, 0, row)
}
function startDrag(index, event) {
  draggingIndex.value = index
  event.dataTransfer.effectAllowed = 'move'
}
function dropField(index) {
  moveField(draggingIndex.value, index)
  draggingIndex.value = -1
}
function resetFields() {
  const original = draft.value._default_field_configs?.[activeAction.value]
  if (original) draft.value.field_configs[activeAction.value] = clone(original)
}
function cleanPayload() {
  const payload = clone(draft.value)
  Object.keys(payload).filter(key => key.startsWith('_')).forEach(key => delete payload[key])
  delete payload.libraries
  delete payload.fetch_metadata
  delete payload.lookup_ip
  payload.types = actionOrder.filter(action => (payload.types || []).includes(action))
  return payload
}
function saveConfig() {
  emit('save', cleanPayload())
  saved.value = true
  window.setTimeout(() => { saved.value = false }, 1800)
}
function enabledFieldCount(action) {
  return (draft.value.field_configs?.[action] || []).filter(row => row.enabled).length
}
</script>

<template>
  <div class="notify-config">
    <header class="page-header">
      <div>
        <div class="eyebrow">MEDIA LIBRARY NOTIFICATIONS</div>
        <h1>媒体库通知</h1>
        <p>选择通知类型，设置需要展示的内容和顺序。</p>
      </div>
      <VBtn class="settings-button" variant="tonal" prepend-icon="mdi-tune-variant" @click="settingsOpen = true">
        设置
      </VBtn>
    </header>

    <VAlert v-if="!draft.enabled" class="mb-5" type="warning" variant="tonal" icon="mdi-bell-off-outline">
      插件当前未启用。你仍可编辑模板，启用后才会发送通知。
    </VAlert>

    <section class="card-grid" aria-label="通知类型">
      <VCard
        v-for="action in actionOrder"
        :key="action"
        class="event-card"
        :class="{ 'event-card--disabled': !isEnabled(action) }"
        variant="outlined"
        tabindex="0"
        @click="openEditor(action)"
        @keydown.enter="openEditor(action)"
      >
        <VCardText class="event-card__body">
          <div class="event-card__top">
            <div class="event-icon"><VIcon :icon="actionMetaFallback[action].icon" size="26" /></div>
            <VSwitch
              :model-value="isEnabled(action)"
              color="primary"
              hide-details
              density="compact"
              :aria-label="`启用${actionMeta(action).label}`"
              @click.stop
              @update:model-value="setEnabled(action, $event)"
            />
          </div>
          <div class="event-card__copy">
            <h2>{{ actionMeta(action).label }}</h2>
            <p>{{ actionMeta(action).description }}</p>
          </div>
        </VCardText>
        <div class="event-card__status">
          <span class="status-dot" :class="{ 'status-dot--off': !isEnabled(action) }" />
          <span>{{ isEnabled(action) ? `已启用 · ${enabledFieldCount(action)} 个字段` : '已停用' }}</span>
          <VIcon class="ml-auto" icon="mdi-chevron-right" size="20" />
        </div>
      </VCard>
    </section>

    <footer class="page-actions">
      <span class="save-hint"><VIcon icon="mdi-information-outline" size="18" /> 字段没有数据时会自动隐藏整行</span>
      <div class="d-flex ga-2">
        <VBtn variant="text" @click="$emit('close')">取消</VBtn>
        <VBtn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveConfig">
          {{ saved ? '已保存' : '保存设置' }}
        </VBtn>
      </div>
    </footer>

    <VDialog v-model="editorOpen" max-width="760" scrollable>
      <VCard class="editor-dialog">
        <VCardTitle class="dialog-header">
          <div class="dialog-title-icon"><VIcon :icon="actionMetaFallback[activeAction].icon" /></div>
          <div><div class="dialog-kicker">通知内容</div><div>{{ activeMeta.label }}</div></div>
          <VBtn class="ml-auto" icon="mdi-close" variant="text" @click="editorOpen = false" />
        </VCardTitle>
        <VCardText class="dialog-body">
          <div class="message-preview">
            <div class="message-preview__title">{{ activeMeta.label }}</div>
            <div v-if="!['auth_success', 'auth_failed', 'test'].includes(activeAction)" class="message-preview__media">示例影片 (2026)</div>
            <div class="message-preview__note">下方勾选的字段将按当前顺序继续展示</div>
          </div>

          <div class="field-list-heading">
            <div><strong>可通知内容</strong><span>拖动左侧手柄排序，只能修改展示名称</span></div>
            <VBtn size="small" variant="text" prepend-icon="mdi-restore" @click="resetFields">恢复默认</VBtn>
          </div>

          <div class="field-list">
            <div
              v-for="(row, index) in activeFields"
              :key="row.key"
              class="field-row"
              :class="{ 'field-row--disabled': !row.enabled }"
              @dragover.prevent
              @drop.prevent="dropField(index)"
            >
              <button
                class="drag-handle"
                type="button"
                draggable="true"
                :aria-label="`拖动${row.label}排序`"
                @dragstart="startDrag(index, $event)"
                @dragend="draggingIndex = -1"
              ><VIcon icon="mdi-drag-vertical" /></button>
              <div class="field-identity">
                <div class="field-key">{{ fieldMeta(row.key).label }}</div>
                <VTextField
                  v-model="row.label"
                  label="展示名称"
                  density="compact"
                  variant="outlined"
                  maxlength="30"
                  hide-details
                />
              </div>
              <div class="field-order-buttons">
                <VBtn :disabled="index === 0" icon="mdi-chevron-up" size="x-small" variant="text" @click="moveField(index, index - 1)" />
                <VBtn :disabled="index === activeFields.length - 1" icon="mdi-chevron-down" size="x-small" variant="text" @click="moveField(index, index + 1)" />
              </div>
              <VCheckbox v-model="row.enabled" color="primary" hide-details :aria-label="`展示${row.label}`" />
            </div>
          </div>
        </VCardText>
        <VCardActions class="dialog-actions">
          <span>{{ enabledFieldCount(activeAction) }} / {{ activeFields.length }} 个字段已启用</span>
          <VBtn color="primary" variant="flat" @click="editorOpen = false">完成</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog v-model="settingsOpen" max-width="720" scrollable>
      <VCard class="settings-dialog">
        <VCardTitle class="dialog-header">
          <div class="dialog-title-icon"><VIcon icon="mdi-tune-variant" /></div>
          <div><div class="dialog-kicker">GLOBAL SETTINGS</div><div>通知设置</div></div>
          <VBtn class="ml-auto" icon="mdi-close" variant="text" @click="settingsOpen = false" />
        </VCardTitle>
        <VCardText class="dialog-body settings-stack">
          <div class="setting-row setting-row--featured">
            <div><strong>启用插件</strong><span>接收媒体服务器事件并发送通知</span></div>
            <VSwitch v-model="draft.enabled" color="primary" hide-details />
          </div>

          <div class="setting-block">
            <label>媒体服务器</label>
            <VSelect
              v-model="draft.mediaservers"
              :items="serverOptions"
              item-title="title"
              item-value="value"
              placeholder="未选择时监听全部媒体服务器"
              multiple
              chips
              closable-chips
              clearable
              variant="outlined"
              hide-details
            />
            <small>选择需要接收通知的 Emby、Jellyfin 或 Plex 实例。</small>
          </div>

          <div class="setting-row">
            <div><strong>聚合剧集入库</strong><span>同一剧集在窗口内只发送一条通知</span></div>
            <VSwitch v-model="draft.aggregate_enabled" color="primary" hide-details />
          </div>
          <VTextField v-if="draft.aggregate_enabled" v-model.number="draft.aggregate_time" label="聚合窗口（秒）" type="number" min="1" variant="outlined" hide-details />

          <div class="settings-grid">
            <VTextField v-model.number="draft.dedupe_library" label="入库/删除去重（秒）" type="number" min="0" variant="outlined" hide-details />
            <VTextField v-model.number="draft.dedupe_playback" label="播放事件去重（秒）" type="number" min="0" variant="outlined" hide-details />
          </div>

          <div class="setting-row"><div><strong>停止时发送待聚合消息</strong><span>插件重载或停止时不丢弃队列</span></div><VSwitch v-model="draft.flush_on_stop" color="primary" hide-details /></div>

          <div class="setting-block test-block">
            <label>测试通知</label>
            <div class="settings-grid settings-grid--test">
              <VSelect v-model="draft.preview_type" :items="actionOrder.map(value => ({ value, title: actionMeta(value).label }))" label="通知类型" variant="outlined" hide-details />
              <VSwitch v-model="draft.send_test" label="保存时发送" color="primary" hide-details />
            </div>
          </div>

          <VAlert type="info" variant="tonal" icon="mdi-message-badge-outline">
            消息渠道遵循 MoviePilot 全局设置，通知类型固定为“媒体库”。
          </VAlert>
        </VCardText>
        <VCardActions class="dialog-actions"><span>设置随主页面一起保存</span><VBtn color="primary" variant="flat" @click="settingsOpen = false">完成</VBtn></VCardActions>
      </VCard>
    </VDialog>
  </div>
</template>

<style scoped>
.notify-config { --surface-soft: rgba(var(--v-theme-on-surface), .045); --line: rgba(var(--v-border-color), .18); padding: 8px 4px 4px; color: rgb(var(--v-theme-on-surface)); }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
.eyebrow, .dialog-kicker { color: rgb(var(--v-theme-primary)); font-size: 11px; font-weight: 750; letter-spacing: .13em; }
h1 { margin: 3px 0 4px; font-size: clamp(28px, 4vw, 38px); line-height: 1.15; letter-spacing: -.035em; }
.page-header p { margin: 0; color: rgba(var(--v-theme-on-surface), .62); }
.settings-button { margin-top: 8px; }
.card-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.event-card { cursor: pointer; border-color: var(--line); border-radius: 18px; overflow: hidden; transition: border-color .18s ease, transform .18s ease, background-color .18s ease; }
.event-card:hover, .event-card:focus-visible { border-color: rgba(var(--v-theme-primary), .66); background: rgba(var(--v-theme-primary), .035); transform: translateY(-1px); outline: none; }
.event-card--disabled { opacity: .68; }
.event-card__body { min-height: 136px; padding: 14px 14px 10px; }
.event-card__top { display: flex; align-items: center; justify-content: space-between; }
.event-icon, .dialog-title-icon { display: grid; place-items: center; width: 40px; height: 40px; color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), .12); border-radius: 12px; }
.event-card__copy { margin-top: 14px; }
.event-card__copy h2 { margin: 0 0 4px; font-size: 16px; line-height: 1.3; }
.event-card__copy p { margin: 0; min-height: 42px; color: rgba(var(--v-theme-on-surface), .58); font-size: 13px; line-height: 1.55; }
.event-card__status { display: flex; align-items: center; gap: 7px; min-height: 38px; padding: 0 14px; border-top: 1px solid var(--line); background: var(--surface-soft); color: rgba(var(--v-theme-on-surface), .65); font-size: 11px; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: rgb(var(--v-theme-success)); box-shadow: 0 0 0 3px rgba(var(--v-theme-success), .12); }
.status-dot--off { background: rgba(var(--v-theme-on-surface), .36); box-shadow: none; }
.page-actions { position: sticky; bottom: 0; z-index: 3; display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 22px; padding: 14px 0 6px; background: rgb(var(--v-theme-surface)); }
.save-hint { display: flex; align-items: center; gap: 7px; color: rgba(var(--v-theme-on-surface), .58); font-size: 12px; }
.editor-dialog, .settings-dialog { border-radius: 20px !important; }
.dialog-header { display: flex; align-items: center; gap: 13px; padding: 20px 22px 16px; border-bottom: 1px solid var(--line); }
.dialog-title-icon { width: 42px; height: 42px; border-radius: 12px; }
.dialog-body { padding: 20px 22px 22px !important; }
.message-preview { padding: 18px; border: 1px solid var(--line); border-radius: 15px; background: var(--surface-soft); }
.message-preview__title { font-size: 17px; font-weight: 700; }
.message-preview__media { margin-top: 3px; font-size: 16px; }
.message-preview__note { margin-top: 13px; color: rgba(var(--v-theme-on-surface), .5); font-size: 12px; }
.field-list-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 24px 2px 10px; }
.field-list-heading strong, .field-list-heading span { display: block; }
.field-list-heading span { margin-top: 2px; color: rgba(var(--v-theme-on-surface), .52); font-size: 12px; }
.field-list { display: grid; gap: 8px; }
.field-row { display: grid; grid-template-columns: 40px minmax(0, 1fr) auto 42px; align-items: center; gap: 10px; padding: 10px; border: 1px solid var(--line); border-radius: 13px; background: rgb(var(--v-theme-surface)); }
.field-row--disabled { opacity: .6; }
.drag-handle { width: 36px; height: 40px; color: rgba(var(--v-theme-on-surface), .46); cursor: grab; border: 0; background: transparent; border-radius: 8px; }
.drag-handle:active { cursor: grabbing; }
.field-identity { display: grid; grid-template-columns: minmax(84px, .55fr) minmax(150px, 1fr); align-items: center; gap: 12px; }
.field-key { color: rgba(var(--v-theme-on-surface), .62); font-size: 13px; }
.field-order-buttons { display: flex; }
.dialog-actions { display: flex; justify-content: space-between; min-height: 66px; padding: 12px 22px !important; border-top: 1px solid var(--line); color: rgba(var(--v-theme-on-surface), .56); font-size: 12px; }
.settings-stack { display: grid; gap: 14px; }
.setting-row { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 14px 16px; border: 1px solid var(--line); border-radius: 14px; }
.setting-row--featured { border-color: rgba(var(--v-theme-primary), .32); background: rgba(var(--v-theme-primary), .055); }
.setting-row strong, .setting-row span { display: block; }
.setting-row span { margin-top: 3px; color: rgba(var(--v-theme-on-surface), .52); font-size: 12px; }
.setting-block { display: grid; gap: 8px; padding: 15px 16px; border: 1px solid var(--line); border-radius: 14px; }
.setting-block label { font-size: 14px; font-weight: 650; }
.setting-block small { color: rgba(var(--v-theme-on-surface), .5); }
.settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.settings-grid--test { align-items: center; }
@media (max-width: 1040px) {
  .card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 680px) {
  .notify-config { padding-top: 0; }
  .page-header { align-items: center; }
  .page-header p, .eyebrow { display: none; }
  h1 { font-size: 26px; }
  .card-grid { grid-template-columns: 1fr; }
  .event-card__body { min-height: 132px; }
  .field-row { grid-template-columns: 34px minmax(0, 1fr) 42px; }
  .field-identity { grid-template-columns: 1fr; gap: 5px; }
  .field-order-buttons { display: none; }
  .page-actions { align-items: flex-end; }
  .save-hint { max-width: 150px; }
  .settings-grid { grid-template-columns: 1fr; }
}
</style>
