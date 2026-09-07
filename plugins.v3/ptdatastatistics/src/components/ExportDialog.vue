<script setup>
import { computed, ref, watch } from 'vue'
import { downloadApiFile, openNativePicker, withQuery } from '../utils'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  api: { type: Object, default: () => ({}) },
  pluginBase: { type: String, required: true },
  sites: { type: Array, default: () => [] },
  fields: { type: Array, default: () => [] },
  firstDay: { type: String, default: '' },
  lastDay: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])
const selectedSiteIds = ref([])
const selectedFields = ref([])
const startDay = ref('')
const endDay = ref('')
const downloading = ref(false)

const opened = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})

watch(
  () => props.modelValue,
  value => {
    if (!value) return
    selectedSiteIds.value = props.sites.map(item => item.site_id).filter(Boolean)
    selectedFields.value = props.fields.map(item => item.key)
    startDay.value = props.firstDay || props.lastDay
    endDay.value = props.lastDay
  },
)

async function download() {
  downloading.value = true
  try {
    const path = withQuery(`${props.pluginBase}/export/csv`, {
      start_day: startDay.value,
      end_day: endDay.value,
      site_ids: selectedSiteIds.value,
      fields: selectedFields.value,
    })
    const suffix = `${startDay.value || 'all'}-${endDay.value || 'latest'}`
    await downloadApiFile(
      props.api,
      path,
      `pt-data-${suffix}.csv`,
      'text/csv;charset=utf-8',
    )
  } finally {
    downloading.value = false
  }
}
</script>

<template>
  <VDialog v-model="opened" max-width="820" scrollable>
    <VCard rounded="xl">
      <VCardTitle class="d-flex align-center ga-2 pa-5">
        <VIcon icon="mdi-file-export-outline" color="primary" />
        导出历史数据
      </VCardTitle>
      <VDivider />
      <VCardText class="pa-5">
        <VRow>
          <VCol cols="12" sm="6">
            <VTextField v-model="startDay" type="date" label="开始日期" variant="outlined" density="comfortable" @click="openNativePicker" />
          </VCol>
          <VCol cols="12" sm="6">
            <VTextField v-model="endDay" type="date" label="结束日期" variant="outlined" density="comfortable" @click="openNativePicker" />
          </VCol>
          <VCol cols="12">
            <VSelect
              v-model="selectedSiteIds"
              :items="sites"
              item-title="site_name"
              item-value="site_id"
              label="选择站点"
              multiple
              chips
              closable-chips
              variant="outlined"
            />
          </VCol>
          <VCol cols="12">
            <div class="text-subtitle-2 mb-3">导出字段</div>
            <div class="field-grid">
              <VCheckbox
                v-for="field in fields"
                :key="field.key"
                v-model="selectedFields"
                :value="field.key"
                :label="field.label"
                density="compact"
                hide-details
              />
            </div>
          </VCol>
        </VRow>
      </VCardText>
      <VDivider />
      <VCardActions class="pa-4 justify-end">
        <VBtn variant="text" @click="opened = false">取消</VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="mdi-file-delimited-outline"
          :loading="downloading"
          :disabled="!selectedFields.length"
          @click="download"
        >CSV</VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>

<style scoped>
.field-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 4px 14px;
}

@media (max-width: 650px) {
  .field-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
