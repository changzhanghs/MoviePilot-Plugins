<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import SiteAvatar from './SiteAvatar.vue'
import { formatBytes, siteColors, unwrapResponse } from '../utils'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  config: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'PTDataStatistics' },
  sourcePluginId: { type: String, default: '' },
  nativeSubscribe: { type: Function, default: null },
  allowRefresh: { type: Boolean, default: true },
})

const loading = ref(false)
const overview = ref({
  server_date: '',
  summary: {},
  today_sites: [],
})
let refreshTimer

const pluginBase = computed(() => `plugin/${props.pluginId || 'PTDataStatistics'}`)
const sites = computed(() => overview.value.today_sites || [])

const donutBackground = computed(() => {
  if (!sites.value.length) return 'conic-gradient(rgba(var(--v-theme-on-surface), .1) 0 100%)'
  let offset = 0
  const stops = sites.value.map((site, index) => {
    const start = offset
    offset += Number(site.contribution || 0)
    return `${siteColors[index % siteColors.length]} ${start}% ${Math.min(offset, 100)}%`
  })
  if (offset < 100) stops.push(`rgba(var(--v-theme-on-surface), .1) ${offset}% 100%`)
  return `conic-gradient(${stops.join(', ')})`
})

async function loadOverview() {
  if (!props.allowRefresh && overview.value.server_date) return
  loading.value = true
  try {
    const data = await props.api.get(`${pluginBase.value}/overview`, { feedback: 'silent' })
    overview.value = unwrapResponse(data) || overview.value
  } finally {
    loading.value = false
  }
}

watch(() => props.allowRefresh, enabled => enabled && loadOverview())

onMounted(() => {
  loadOverview()
  refreshTimer = window.setInterval(loadOverview, 60000)
})

onUnmounted(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<template>
  <div class="pt-dashboard">
    <div class="pt-dashboard__header">
      <div class="pt-dashboard__totals">
        <div class="total-pill">
          <VIcon class="total-pill__icon" icon="mdi-calendar-blank-outline" size="20" />
          <span>统计日期</span>
          <strong>{{ overview.server_date || '暂无' }}</strong>
        </div>
        <div class="total-pill total-pill--upload">
          <VIcon class="total-pill__icon" icon="mdi-arrow-up" size="20" color="success" />
          <span>上传增量</span>
          <strong>{{ formatBytes(overview.summary.today_upload) }}</strong>
        </div>
        <div class="total-pill total-pill--download">
          <VIcon class="total-pill__icon" icon="mdi-arrow-down" size="20" color="error" />
          <span>下载增量</span>
          <strong>{{ formatBytes(overview.summary.today_download) }}</strong>
        </div>
      </div>
      <VProgressLinear v-if="loading" indeterminate color="primary" height="2" />
    </div>

    <div v-if="sites.length" class="pt-dashboard__body">
      <div class="donut-wrap">
        <div class="donut" :style="{ background: donutBackground }">
          <div class="donut__hole">
            <strong>{{ sites.length }}</strong>
            <span>个站点</span>
          </div>
        </div>
      </div>

      <div class="site-scroll">
        <div v-for="(site, index) in sites" :key="site.site_id || site.site_name" class="site-row">
          <div class="site-row__avatar"><SiteAvatar :api="api" :site="site" :size="36" /></div>
          <div class="site-row__name">
            <strong>{{ site.site_name }}</strong>
          </div>
          <div class="site-row__metric site-row__metric--upload">↑ {{ formatBytes(site.daily_upload) }}</div>
          <div class="site-row__metric site-row__metric--download">↓ {{ formatBytes(site.daily_download) }}</div>
          <div class="site-row__share">
            <i :style="{ backgroundColor: siteColors[index % siteColors.length] }" />
            {{ site.contribution.toFixed(1) }}%
          </div>
        </div>
      </div>
    </div>

    <div v-else class="pt-dashboard__empty">
      <VIcon icon="mdi-chart-donut-variant" size="48" color="secondary" />
      <strong>今日暂无站点流量</strong>
      <span>仅显示今日上传或下载大于零、且基线有效的站点</span>
    </div>
  </div>
</template>

<style scoped>
.pt-dashboard {
  display: flex;
  flex-direction: column;
  min-height: 0;
  max-height: 100%;
  min-width: 0;
  overflow: hidden;
}

.pt-dashboard__header {
  flex: 0 0 auto;
}

.pt-dashboard__totals {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding-bottom: 14px;
}

.total-pill {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  grid-template-areas: 'icon label' 'icon value';
  align-items: center;
  column-gap: 9px;
  padding: 10px 13px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 999px;
  background: rgba(var(--v-theme-surface-variant), .32);
  min-width: 0;
}

.total-pill__icon { grid-area: icon; }
.total-pill span { grid-area: label; font-size: .72rem; color: rgba(var(--v-theme-on-surface), .64); }
.total-pill strong { grid-area: value; overflow-wrap: anywhere; }
.site-row__metric--upload { color: rgb(var(--v-theme-success)); }
.site-row__metric--download { color: rgb(var(--v-theme-error)); }

.pt-dashboard__body {
  display: grid;
  grid-template-columns: minmax(150px, 30%) minmax(0, 1fr);
  gap: 18px;
  min-height: 0;
  flex: 1 1 auto;
}

.donut-wrap {
  display: grid;
  place-items: center;
}

.donut {
  display: grid;
  place-items: center;
  width: clamp(132px, 18vw, 190px);
  aspect-ratio: 1;
  border-radius: 50%;
  box-shadow: 0 12px 32px rgba(0, 0, 0, .16);
}

.donut__hole {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 68%;
  aspect-ratio: 1;
  border-radius: 50%;
  background: rgb(var(--v-theme-surface));
}

.donut__hole strong { font-size: 2rem; line-height: 1; }
.donut__hole span { margin-top: 5px; font-size: .78rem; color: rgba(var(--v-theme-on-surface), .62); }

.site-scroll {
  min-height: 0;
  max-height: min(420px, 55vh);
  overflow-y: auto;
  padding-right: 5px;
}

.site-row {
  display: grid;
  grid-template-columns: auto minmax(100px, 1fr) auto auto auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 9px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 14px;
  background: rgba(var(--v-theme-surface-variant), .2);
}

.site-row__name { display: flex; flex-direction: column; min-width: 0; }
.site-row__avatar { display: flex; }
.site-row__name strong, .site-row__name span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.site-row__name span { font-size: .72rem; color: rgba(var(--v-theme-on-surface), .58); }
.site-row__metric { font-size: .82rem; font-weight: 650; white-space: nowrap; }
.site-row__share { display: flex; align-items: center; gap: 5px; font-size: .78rem; white-space: nowrap; }
.site-row__share i { width: 8px; height: 8px; border-radius: 50%; }

.pt-dashboard__empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-align: center;
  color: rgba(var(--v-theme-on-surface), .64);
}

.pt-dashboard__empty strong { color: rgb(var(--v-theme-on-surface)); }

@media (max-width: 700px) {
  .pt-dashboard__totals { grid-template-columns: 1fr; }
  .pt-dashboard__body { grid-template-columns: 1fr; }
  .donut-wrap { display: none; }
  .site-row {
    grid-template-columns: auto minmax(0, 1fr) minmax(0, 1fr);
    grid-template-areas: 'avatar name name' 'avatar upload download';
  }
  .site-row__avatar { grid-area: avatar; align-self: center; }
  .site-row__name { grid-area: name; }
  .site-row__metric--upload { grid-area: upload; }
  .site-row__metric--download { grid-area: download; text-align: right; }
  .site-row__share { display: none; }
}
</style>
