<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Chart from 'chart.js/auto'
import CareerExportDialog from './CareerExportDialog.vue'
import ExportDialog from './ExportDialog.vue'
import MetricCard from './MetricCard.vue'
import SiteAvatar from './SiteAvatar.vue'
import { formatBytes, formatNumber, openNativePicker, siteColors, unwrapResponse, withQuery } from '../utils'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'PTDataStatistics' },
  initialTab: { type: String, default: 'overview' },
  initialSettings: { type: Object, default: () => ({}) },
  hostManagedConfig: { type: Boolean, default: false },
  showClose: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'action', 'save'])
const hostToast = inject('moviepilot:toast', null)
const activeTab = ref(props.initialTab)
const loading = ref(false)
const saving = ref(false)
const syncing = ref(false)
const historyLoading = ref(false)
const distributionLoading = ref(false)
const error = ref('')
const exportOpen = ref(false)
const careerOpen = ref(false)
const overview = ref({
  server_date: '', generated_at: '', first_history_day: '', last_history_day: '',
  summary: {}, sites: [], today_sites: [], history_sites: [],
  twelve: { joined: 0, total: 12, percent: 0, items: [] },
  retirement: { total: 0, retired: 0, upgrading: 0, rule_missing: 0, sites: [] },
})
const distribution = ref({ month: '', day: '', monthly: [], daily: [] })
const distributionFilters = ref({ month: '', day: '' })
const distributionMetric = ref('upload')
const siteSortKey = ref('upload')
const siteSortOptions = [
  { title: '累计上传', value: 'upload' },
  { title: '累计下载', value: 'download' },
  { title: '魔力', value: 'bonus' },
  { title: '做种数', value: 'seeding' },
  { title: '做种体积', value: 'seeding_size' },
]
let distributionRequestSequence = 0
const exportFields = ref([])
const settingsDraft = ref({
  enabled: false, show_sidebar: true, retention_days: 365,
  notification_enabled: false, notification_cron: '0 9 * * *', notification_modes: ['today'],
})
const history = ref({ start_day: '', end_day: '', count: 0, records: [] })
const historyFilters = ref({ startDay: '', endDay: '', siteIds: [], includeArchived: true })
const historyScope = ref('day')
const selectedHistoryPeriodKey = ref('')
const selectedHistorySiteId = ref(null)
const hourlyTraffic = ref({ day: '', site_id: null, site_name: '全部站点', baseline_valid: false, sample_count: 0, points: [] })
const hourlyLoading = ref(false)
const historyChartCanvas = ref(null)
let historyChart = null
const selectedRetirementSiteKey = ref('')

const pluginBase = computed(() => `plugin/${props.pluginId || 'PTDataStatistics'}`)
const currentSites = computed(() => overview.value.sites || [])
const sortedCurrentSites = computed(() => [...currentSites.value].sort((left, right) => {
  const difference = Number(right?.[siteSortKey.value] ?? -1) - Number(left?.[siteSortKey.value] ?? -1)
  return difference || String(left?.site_name || '').localeCompare(String(right?.site_name || ''), 'zh-CN')
}))
const historySites = computed(() => overview.value.history_sites?.length ? overview.value.history_sites : currentSites.value)
const todaySites = computed(() => overview.value.today_sites || [])
const summary = computed(() => overview.value.summary || {})
const twelveItems = computed(() => overview.value.twelve?.items || [])
const retirement = computed(() => overview.value.retirement || { sites: [] })
const selectedRetirementSite = computed(() => {
  const sites = retirement.value.sites || []
  return sites.find(site => retirementSiteKey(site) === selectedRetirementSiteKey.value) || sites[0] || null
})
const historyGroups = computed(() => {
  const grouped = new Map()
  for (const item of history.value.records || []) {
    const day = item.updated_day || '未知日期'
    const group = grouped.get(day) || {
      day, records: [], siteCount: 0, validCount: 0, upload: 0, download: 0,
      totalUpload: 0, totalDownload: 0, bonus: 0, seeding: 0, seedingSize: 0,
    }
    group.records.push(item)
    group.siteCount += 1
    group.totalUpload += Number(item.upload || 0)
    group.totalDownload += Number(item.download || 0)
    group.bonus += Number(item.bonus || 0)
    group.seeding += Number(item.seeding || 0)
    group.seedingSize += Number(item.seeding_size || 0)
    if (item.baseline_valid) {
      group.validCount += 1
      group.upload += Number(item.daily_upload || 0)
      group.download += Number(item.daily_download || 0)
    }
    grouped.set(day, group)
  }
  return [...grouped.values()].sort((a, b) => b.day.localeCompare(a.day))
})
function summarizePeriod(key, label, startDay, endDay, records) {
  const valid = records.filter(item => item.baseline_valid)
  return {
    key, label, startDay, endDay, records,
    siteCount: new Set(records.map(item => item.site_id || item.site_name)).size,
    validCount: valid.length,
    upload: valid.reduce((sum, item) => sum + Number(item.daily_upload || 0), 0),
    download: valid.reduce((sum, item) => sum + Number(item.daily_download || 0), 0),
  }
}
function weekBounds(day) {
  const value = new Date(`${day}T00:00:00Z`)
  const offset = (value.getUTCDay() + 6) % 7
  const start = new Date(value)
  start.setUTCDate(value.getUTCDate() - offset)
  const end = new Date(start)
  end.setUTCDate(start.getUTCDate() + 6)
  return [start.toISOString().slice(0, 10), end.toISOString().slice(0, 10)]
}
const historyPeriods = computed(() => {
  if (historyScope.value === 'day') {
    return historyGroups.value.map(group => summarizePeriod(
      `day:${group.day}`, group.day, group.day, group.day, group.records,
    ))
  }
  const grouped = new Map()
  for (const item of history.value.records || []) {
    const day = item.updated_day
    if (!day) continue
    let key
    let label
    let startDay
    let endDay
    if (historyScope.value === 'week') {
      ;[startDay, endDay] = weekBounds(day)
      key = `week:${startDay}`
      label = `${startDay.slice(5)} — ${endDay.slice(5)}`
    } else {
      startDay = `${day.slice(0, 7)}-01`
      const next = new Date(`${startDay}T00:00:00Z`)
      next.setUTCMonth(next.getUTCMonth() + 1)
      next.setUTCDate(0)
      endDay = next.toISOString().slice(0, 10)
      key = `month:${day.slice(0, 7)}`
      label = `${day.slice(0, 7)}`
    }
    const bucket = grouped.get(key) || { key, label, startDay, endDay, records: [] }
    bucket.records.push(item)
    grouped.set(key, bucket)
  }
  return [...grouped.values()]
    .map(item => summarizePeriod(item.key, item.label, item.startDay, item.endDay, item.records))
    .sort((a, b) => b.startDay.localeCompare(a.startDay))
})
const selectedHistoryPeriod = computed(() => (
  historyPeriods.value.find(period => period.key === selectedHistoryPeriodKey.value) || historyPeriods.value[0] || null
))
const selectedPeriodSites = computed(() => {
  const grouped = new Map()
  for (const item of selectedHistoryPeriod.value?.records || []) {
    const key = String(item.site_id || item.site_name)
    const current = grouped.get(key) || {
      ...item, period_upload: 0, period_download: 0, valid_count: 0,
    }
    if (String(item.updated_day || '') >= String(current.updated_day || '')) Object.assign(current, item)
    if (item.baseline_valid) {
      current.period_upload += Number(item.daily_upload || 0)
      current.period_download += Number(item.daily_download || 0)
      current.valid_count += 1
    }
    grouped.set(key, current)
  }
  return [...grouped.values()].sort((a, b) => (
    b.period_upload + b.period_download - a.period_upload - a.period_download
  ) || String(a.site_name).localeCompare(String(b.site_name), 'zh-CN'))
})
const selectedHistorySite = computed(() => (
  selectedPeriodSites.value.find(item => Number(item.site_id) === Number(selectedHistorySiteId.value)) || null
))
const selectedHistoryRecords = computed(() => {
  if (!selectedHistoryPeriod.value || !selectedHistorySiteId.value) return []
  return [...(selectedHistoryPeriod.value.records || [])]
    .filter(item => Number(item.site_id) === Number(selectedHistorySiteId.value))
    .sort((left, right) => String(right.updated_day || '').localeCompare(String(left.updated_day || '')))
})
const historyChartSeries = computed(() => {
  if (!selectedHistoryPeriod.value) return []
  if (historyScope.value === 'day') {
    return (hourlyTraffic.value.points || []).map(point => ({
      label: point.hour, upload: Number(point.upload || 0), download: Number(point.download || 0),
    }))
  }
  const grouped = new Map()
  for (const item of selectedHistoryPeriod.value.records || []) {
    if (selectedHistorySiteId.value && Number(item.site_id) !== Number(selectedHistorySiteId.value)) continue
    if (!item.baseline_valid) continue
    const value = grouped.get(item.updated_day) || { label: item.updated_day.slice(5), upload: 0, download: 0 }
    value.upload += Number(item.daily_upload || 0)
    value.download += Number(item.daily_download || 0)
    grouped.set(item.updated_day, value)
  }
  return [...grouped.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([, value]) => value)
})

function notify(message, type = 'success') {
  const method = ['success', 'info', 'warning', 'error'].includes(type) ? type : 'success'
  if (typeof hostToast?.[method] === 'function') hostToast[method](message)
  else if (method === 'error') error.value = message
}
function field(value, digits = 2) {
  return value === '' || value === null || value === undefined ? '站点未提供' : formatNumber(value, digits)
}
function bonusValue(value) {
  return value === '' || value === null || value === undefined ? '暂无魔力数据' : formatNumber(value, 2)
}
function estimatedBonusHourly(value) {
  return value === null || value === undefined
    ? '暂不可估算'
    : `${formatNumber(value, 2)} / 小时`
}
function selectHistoryPeriod(period) {
  selectedHistoryPeriodKey.value = period.key
  selectedHistorySiteId.value = null
}
function selectHistorySite(item) {
  const value = item?.site_id ? Number(item.site_id) : null
  if (value === null) {
    selectedHistorySiteId.value = null
    return
  }
  selectedHistorySiteId.value = Number(selectedHistorySiteId.value) === value ? null : value
}
async function loadHourlyTraffic() {
  const period = selectedHistoryPeriod.value
  if (historyScope.value !== 'day' || !period) return
  hourlyLoading.value = true
  try {
    const response = await props.api.get(withQuery(`${pluginBase.value}/history/hourly`, {
      day: period.startDay,
      site_id: selectedHistorySiteId.value || '',
    }), { feedback: 'silent' })
    hourlyTraffic.value = unwrapResponse(response) || hourlyTraffic.value
  } catch (err) {
    notify(err?.message || '加载小时流量失败', 'error')
    hourlyTraffic.value = { day: period.startDay, site_id: selectedHistorySiteId.value, site_name: selectedHistorySite.value?.site_name || '全部站点', baseline_valid: false, sample_count: 0, points: [] }
  } finally {
    hourlyLoading.value = false
  }
}
function setHistoryChartCanvas(element) {
  if (element) historyChartCanvas.value = element
}
function renderHistoryChart() {
  if (historyChart) {
    historyChart.destroy()
    historyChart = null
  }
  if (!historyChartCanvas.value || !historyChartSeries.value.length) return
  const context = historyChartCanvas.value.getContext('2d')
  historyChart = new Chart(context, {
    type: 'line',
    data: {
      labels: historyChartSeries.value.map(item => item.label),
      datasets: [
        {
          label: '上传',
          data: historyChartSeries.value.map(item => item.upload),
          borderColor: '#74d83f',
          backgroundColor: 'rgba(116,216,63,.12)',
          pointBackgroundColor: '#74d83f',
          pointRadius: historyScope.value === 'day' ? 2 : 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: .34,
          fill: true,
        },
        {
          label: '下载',
          data: historyChartSeries.value.map(item => item.download),
          borderColor: '#ff5364',
          backgroundColor: 'rgba(255,83,100,.10)',
          pointBackgroundColor: '#ff5364',
          pointRadius: historyScope.value === 'day' ? 2 : 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: .34,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      animation: { duration: 220 },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: context => `${context.dataset.label}：${formatBytes(context.raw)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: 'rgba(210,218,238,.58)', maxRotation: 0, autoSkip: true, maxTicksLimit: historyScope.value === 'day' ? 12 : 16 },
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(210,218,238,.08)' },
          ticks: { color: 'rgba(210,218,238,.58)', callback: value => formatBytes(value) },
        },
      },
    },
  })
}
function stateMeta(state) {
  if (state === 'joined') return { label: '已加入', color: 'success', icon: 'mdi-check-circle' }
  if (state === 'waiting') return { label: '待数据', color: 'warning', icon: 'mdi-clock-outline' }
  return { label: '未加入', color: 'secondary', icon: 'mdi-lock-outline' }
}
function retirementMeta(status) {
  if (status === 'retired') return { label: '已养老', color: 'success', icon: 'mdi-shield-check-outline' }
  if (status === 'upgrading') return { label: '升级中', color: 'warning', icon: 'mdi-trending-up' }
  return { label: '规则缺失', color: 'secondary', icon: 'mdi-help-circle-outline' }
}
function retirementSiteKey(site) {
  return String(site?.site_id || site?.site_name || '')
}
function selectRetirementSite(site) {
  selectedRetirementSiteKey.value = retirementSiteKey(site)
}
function setDefaultRanges() {
  const end = overview.value.last_history_day || overview.value.server_date
  if (!end) return
  if (!historyFilters.value.endDay) {
    const startDate = new Date(`${end}T00:00:00`)
    startDate.setDate(startDate.getDate() - 29)
    historyFilters.value.endDay = end
    historyFilters.value.startDay = startDate.toISOString().slice(0, 10)
    historyFilters.value.siteIds = []
  }
  if (!distributionFilters.value.day) distributionFilters.value.day = end
  if (!distributionFilters.value.month) distributionFilters.value.month = end.slice(0, 7)
}
async function loadDistribution() {
  const filters = { ...distributionFilters.value }
  if (!filters.month || !filters.day) return
  const requestSequence = ++distributionRequestSequence
  distributionLoading.value = true
  try {
    const path = withQuery(`${pluginBase.value}/distribution`, filters)
    const response = unwrapResponse(await props.api.get(path, { feedback: 'silent' }))
    if (requestSequence === distributionRequestSequence && response) distribution.value = response
  } catch (err) {
    if (requestSequence === distributionRequestSequence) notify(err?.message || '加载流量分布失败', 'error')
  } finally {
    if (requestSequence === distributionRequestSequence) distributionLoading.value = false
  }
}
function updateDistributionFilter(key, value) {
  distributionFilters.value = { ...distributionFilters.value, [key]: value || '' }
  if (value) {
    loadDistribution()
  } else {
    distributionRequestSequence += 1
    distributionLoading.value = false
  }
}
async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [overviewData, settingsData] = await Promise.all([
      props.api.get(`${pluginBase.value}/overview`, { feedback: 'silent' }),
      props.api.get(`${pluginBase.value}/settings`, { feedback: 'silent' }),
    ])
    overview.value = unwrapResponse(overviewData) || overview.value
    const parsed = unwrapResponse(settingsData) || {}
    const hostSettings = props.hostManagedConfig && Object.keys(props.initialSettings || {}).length
      ? props.initialSettings
      : {}
    settingsDraft.value = JSON.parse(JSON.stringify({
      ...settingsDraft.value,
      ...(parsed.settings || {}),
      ...hostSettings,
    }))
    exportFields.value = parsed.export_fields || []
    setDefaultRanges()
    await loadDistribution()
  } catch (err) {
    error.value = err?.message || '加载 PT 数据统计失败'
  } finally {
    loading.value = false
  }
}
async function syncFromMP() {
  syncing.value = true
  try {
    const result = unwrapResponse(await props.api.post(`${pluginBase.value}/sync`, {})) || {}
    await loadAll()
    await loadHistory()
    notify(`已同步 MoviePilot 数据：写入 ${result.imported || 0} 条`)
    emit('action')
  } catch (err) {
    notify(err?.message || '同步 MoviePilot 数据失败', 'error')
  } finally {
    syncing.value = false
  }
}
async function loadHistory() {
  historyLoading.value = true
  try {
    const path = withQuery(`${pluginBase.value}/history`, {
      start_day: historyFilters.value.startDay, end_day: historyFilters.value.endDay,
      site_ids: historyFilters.value.siteIds, include_archived: historyFilters.value.includeArchived, limit: 50000,
    })
    history.value = unwrapResponse(await props.api.get(path, { feedback: 'silent' })) || history.value
    selectedHistoryPeriodKey.value = historyPeriods.value[0]?.key || ''
    selectedHistorySiteId.value = null
  } catch (err) {
    notify(err?.message || '查询历史数据失败', 'error')
  } finally {
    historyLoading.value = false
  }
}
async function saveSettings() {
  saving.value = true
  try {
    const payload = JSON.parse(JSON.stringify(settingsDraft.value))
    delete payload.sync_interval_minutes
    if (props.hostManagedConfig) {
      emit('save', payload)
      return
    }
    const data = unwrapResponse(await props.api.post(`${pluginBase.value}/settings`, payload)) || {}
    settingsDraft.value = JSON.parse(JSON.stringify(data.settings || settingsDraft.value))
    exportFields.value = data.export_fields || exportFields.value
    notify('设置已保存')
    emit('action')
  } catch (err) {
    notify(err?.message || '保存设置失败', 'error')
  } finally {
    saving.value = false
  }
}
function distributionSegments(items) {
  const key = distributionMetric.value
  const total = (items || []).reduce((sum, item) => sum + Number(item[key] || 0), 0)
  return (items || []).filter(item => Number(item[key] || 0) > 0).map((item, index) => ({
    ...item, value: Number(item[key] || 0), percent: total ? Number(item[key] || 0) * 100 / total : 0,
    color: siteColors[index % siteColors.length],
  }))
}
function donutStyle(items) {
  const segments = distributionSegments(items)
  if (!segments.length) return { background: 'conic-gradient(rgba(var(--v-theme-on-surface), .1) 0 100%)' }
  let offset = 0
  const stops = segments.map(segment => {
    const start = offset
    offset += segment.percent
    return `${segment.color} ${start}% ${Math.min(offset, 100)}%`
  })
  return { background: `conic-gradient(${stops.join(', ')})` }
}
function nextLevelRule(site) {
  return (site.route || []).find(level => level.name === site.next_level) || null
}
function retirementRule(site) {
  return (site.route || []).find(level => level.is_retirement) || null
}
function estimatedLevelDate(level) {
  if (!level) return '注册时间暂无法预估'
  const eligibleDate = level.eligible_date || ''
  const serverDate = overview.value.server_date || ''
  if (level.reached || (eligibleDate && serverDate && eligibleDate <= serverDate)) return '注册时间已达成'
  return eligibleDate ? `预计达成日期 ${eligibleDate}` : '注册时间暂无法预估'
}
function retirementRoute(site) {
  const route = site.route || []
  const retirementIndex = route.findIndex(level => level.is_retirement)
  return retirementIndex >= 0 ? route.slice(0, retirementIndex + 1) : route
}
function retirementProgressPercent(site) {
  const route = retirementRoute(site)
  if (!route.length) return 0
  if (route.length === 1) return route[0].reached ? 100 : 0
  let reachedIndex = -1
  route.forEach((level, index) => {
    if (level.reached) reachedIndex = index
  })
  return Math.max(0, Math.min(100, reachedIndex * 100 / (route.length - 1)))
}
function durationLabel(days) {
  const value = Number(days || 0)
  if (!value) return '无限制'
  return value % 7 === 0 ? `${value / 7} 周` : `${value} 天`
}
function elapsedAccountDays(site) {
  const startText = String(site?.join_at || '').slice(0, 10)
  const endText = String(overview.value.server_date || site?.updated_day || '').slice(0, 10)
  if (!startText || !endText) return null
  const start = Date.parse(`${startText}T00:00:00Z`)
  const end = Date.parse(`${endText}T00:00:00Z`)
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null
  return Math.max(0, Math.floor((end - start) / 86400000))
}
function requirementRows(site, level) {
  if (!site || !level) return []
  const rows = []
  const reached = Boolean(level.reached)
  const pushNumeric = ({ key, label, icon, current, target, formatter, strict = false, unavailable = false }) => {
    if (!(Number(target) > 0)) return
    const currentNumber = Number(current)
    const targetNumber = Number(target)
    const available = !unavailable && Number.isFinite(currentNumber)
    const complete = reached || (available && (strict ? currentNumber > targetNumber : currentNumber >= targetNumber))
    const progress = complete ? 100 : available ? Math.max(0, Math.min(100, currentNumber * 100 / targetNumber)) : 0
    const difference = available ? Math.max(targetNumber - currentNumber, 0) : null
    rows.push({
      key,
      label,
      icon,
      current: available ? formatter(currentNumber) : '数据未提供',
      target: `${strict ? '>' : '≥'} ${formatter(targetNumber)}`,
      detail: unavailable ? '数据未提供' : complete ? '已达成' : difference === null ? '数据未提供' : `还差 ${formatter(difference)}`,
      complete,
      unavailable: !available,
      progress,
    })
  }

  if (level.min_join_days) {
    const currentDays = elapsedAccountDays(site)
    const strict = Boolean(level.min_join_days_strict)
    const complete = reached || (currentDays !== null && (strict ? currentDays > level.min_join_days : currentDays >= level.min_join_days))
    const requiredDays = Number(level.min_join_days) + (strict ? 1 : 0)
    rows.push({
      key: 'join-time',
      label: '注册时间',
      icon: 'mdi-calendar-check-outline',
      current: complete ? '注册时间已达成' : currentDays === null ? '加入时间未提供' : `已注册 ${durationLabel(currentDays)}`,
      target: `${strict ? '>' : '≥'} ${durationLabel(level.min_join_days)}`,
      detail: complete ? '已达成' : currentDays === null ? '加入时间未提供' : `还差 ${durationLabel(requiredDays - currentDays)}`,
      complete,
      unavailable: currentDays === null,
      progress: complete ? 100 : currentDays === null ? 0 : Math.max(0, Math.min(100, currentDays * 100 / level.min_join_days)),
    })
  }
  pushNumeric({ key: 'upload', label: '上传量', icon: 'mdi-upload-outline', current: site.upload, target: level.min_upload, formatter: formatBytes, strict: level.min_upload_strict })
  pushNumeric({ key: 'download', label: '下载量', icon: 'mdi-download-outline', current: site.download, target: level.min_download, formatter: formatBytes, strict: level.min_download_strict })
  pushNumeric({ key: 'ratio', label: '分享率', icon: 'mdi-chart-donut', current: site.ratio, target: level.min_ratio, formatter: value => formatNumber(value, 2), strict: level.min_ratio_strict })
  pushNumeric({ key: 'seeding-points', label: '做种积分', icon: 'mdi-star-circle-outline', current: site.seeding_points, target: level.min_seeding_points, formatter: value => formatNumber(value, 0), unavailable: site.seeding_points === null || site.seeding_points === undefined })
  pushNumeric({ key: 'bonus', label: '魔力', icon: 'mdi-lightning-bolt-circle', current: site.bonus, target: level.min_bonus, formatter: value => formatNumber(value, 0), unavailable: site.bonus === null || site.bonus === undefined })
  pushNumeric({ key: 'seeding', label: '做种数', icon: 'mdi-seed-outline', current: site.seeding, target: level.min_seeding, formatter: value => formatNumber(value, 0) })
  return rows
}
function levelTrafficRequirement(level) {
  if (level.min_download) return `下载 ${level.min_download_strict ? '>' : '≥'} ${formatBytes(level.min_download)}`
  if (level.min_upload) return `上传 ${level.min_upload_strict ? '>' : '≥'} ${formatBytes(level.min_upload)}`
  return '—'
}
function levelRatioRequirement(level) {
  if (level.min_ratio === null || level.min_ratio === undefined) return '—'
  return `分享率 ${level.min_ratio_strict ? '>' : '≥'} ${formatNumber(level.min_ratio, 2)}`
}
function levelPointsRequirement(level) {
  if (level.min_seeding_points) return `做种积分 ${formatNumber(level.min_seeding_points, 0)}`
  if (level.min_bonus) return `魔力 ${formatNumber(level.min_bonus, 0)}`
  if (level.min_seeding) return `做种 ${formatNumber(level.min_seeding, 0)}`
  return '—'
}
function levelStateLabel(level) {
  if (level.is_current) return '当前'
  if (level.is_retirement) return level.reached ? '已保号' : '保号目标'
  return level.reached ? '已达成' : '待达成'
}
watch(
  () => (retirement.value.sites || []).map(retirementSiteKey).join('|'),
  () => {
    const sites = retirement.value.sites || []
    if (!sites.some(site => retirementSiteKey(site) === selectedRetirementSiteKey.value)) {
      selectedRetirementSiteKey.value = retirementSiteKey(sites[0])
    }
  },
  { immediate: true },
)
watch(
  () => `${historyScope.value}:${historyPeriods.value.map(period => period.key).join('|')}`,
  () => {
    if (!historyPeriods.value.some(period => period.key === selectedHistoryPeriodKey.value)) {
      selectedHistoryPeriodKey.value = historyPeriods.value[0]?.key || ''
    }
    selectedHistorySiteId.value = null
  },
  { immediate: true },
)
watch(
  () => [historyScope.value, selectedHistoryPeriod.value?.key, selectedHistorySiteId.value],
  async () => {
    if (historyScope.value === 'day') await loadHourlyTraffic()
    await nextTick()
    renderHistoryChart()
  },
)
watch(historyChartSeries, async () => {
  await nextTick()
  renderHistoryChart()
}, { deep: true })
watch(activeTab, value => {
  if (value === 'history' && !(history.value.records || []).length) loadHistory()
}, { immediate: true })
onMounted(loadAll)
onBeforeUnmount(() => historyChart?.destroy())
</script>

<template>
  <div class="pt-workbench" :class="{ 'pt-workbench--compact': compact }">
    <VAlert v-if="error" type="error" variant="tonal" closable class="mb-4" @click:close="error = ''">{{ error }}</VAlert>
    <VProgressLinear v-if="loading" indeterminate color="primary" rounded class="mb-3" />
    <div class="workbench-nav">
      <VTabs v-model="activeTab" color="primary" class="workbench-tabs">
        <VTab value="overview" prepend-icon="mdi-view-dashboard-outline">数据总览</VTab>
        <VTab value="retirement" prepend-icon="mdi-shield-star-outline">养老进度</VTab>
        <VTab value="history" prepend-icon="mdi-chart-timeline-variant">数据统计</VTab>
        <VTab value="config" prepend-icon="mdi-tune-variant">设置</VTab>
      </VTabs>
      <div class="workbench-nav__actions">
        <VBtn class="data-refresh-btn" color="primary" variant="flat" prepend-icon="mdi-refresh" :loading="syncing" @click="syncFromMP">数据刷新</VBtn>
        <VBtn v-if="showClose" icon="mdi-close" variant="text" aria-label="关闭" @click="$emit('close')" />
      </div>
    </div>

    <VWindow v-model="activeTab">
      <VWindowItem value="overview">
        <section class="section-block"><div class="metric-grid">
          <MetricCard label="总上传" :value="formatBytes(summary.total_upload)" icon="mdi-arrow-up-bold" color="success" :hint="`${summary.valid_sites || 0} 个有效站点`" />
          <MetricCard label="总下载" :value="formatBytes(summary.total_download)" icon="mdi-arrow-down-bold" color="error" :hint="`总分享率 ${formatNumber(summary.overall_ratio, 3)}`" />
          <MetricCard label="总做种数" :value="formatNumber(summary.total_seeding, 0)" icon="mdi-seed-outline" color="warning" :hint="`做种体积 ${formatBytes(summary.total_seeding_size)}`" />
          <MetricCard label="总做种体积" :value="formatBytes(summary.total_seeding_size)" icon="mdi-database-outline" color="info" :hint="`${summary.valid_sites || 0} 个有效站点`" />
          <MetricCard label="今日上传" :value="formatBytes(summary.today_upload)" icon="mdi-arrow-up-bold" color="success" :hint="`${todaySites.length} 个有流量站点`" />
          <MetricCard label="今日下载" :value="formatBytes(summary.today_download)" icon="mdi-arrow-down-bold" color="error" />
        </div></section>

        <section class="section-block distribution-panel">
          <div class="section-heading distribution-heading">
            <div><span class="section-kicker">TRAFFIC DISTRIBUTION</span><h2>流量分布</h2></div>
            <VBtnToggle v-model="distributionMetric" mandatory color="primary" density="compact" variant="outlined"><VBtn value="upload">上传</VBtn><VBtn value="download">下载</VBtn></VBtnToggle>
          </div>
          <VProgressLinear v-if="distributionLoading" indeterminate color="primary" height="2" class="mb-3" />
          <div class="distribution-grid">
            <article v-for="panel in [{ key: 'monthly', label: '月度分布', inputLabel: '选择月份', icon: 'mdi-calendar-month-outline', dateKey: 'month', type: 'month' }, { key: 'daily', label: '每日分布', inputLabel: '选择日期', icon: 'mdi-calendar-outline', dateKey: 'day', type: 'date' }]" :key="panel.key" class="distribution-card">
              <div class="distribution-card__header">
                <strong>{{ panel.label }}</strong>
                <VTextField
                  :model-value="distributionFilters[panel.dateKey]"
                  class="distribution-date-input"
                  :type="panel.type"
                  :label="panel.inputLabel"
                  :prepend-inner-icon="panel.icon"
                  :max="panel.type === 'month' ? overview.server_date?.slice(0, 7) : overview.server_date"
                  density="compact"
                  variant="outlined"
                  hide-details
                  :aria-label="panel.inputLabel"
                  @click="openNativePicker"
                  @update:model-value="value => updateDistributionFilter(panel.dateKey, value)"
                />
              </div>
              <div v-if="distributionSegments(distribution[panel.key]).length" class="pie-layout">
                <div class="pie" :style="donutStyle(distribution[panel.key])"><div class="pie__hole"><span>{{ distribution[panel.dateKey] }}</span><strong>{{ formatBytes(distributionSegments(distribution[panel.key]).reduce((sum, item) => sum + item.value, 0)) }}</strong></div></div>
                <div class="pie-legend"><div v-for="item in distributionSegments(distribution[panel.key])" :key="item.site_id || item.site_name"><i :style="{ background: item.color }" /><span>{{ item.site_name }}</span><strong>{{ formatBytes(item.value) }}</strong><em>{{ item.percent.toFixed(1) }}%</em></div></div>
              </div>
              <div v-else class="empty-state compact-empty">所选时间暂无有效流量</div>
            </article>
          </div>
        </section>

        <section class="section-block">
          <div class="section-heading site-data-heading">
            <div><span class="section-kicker">CURRENT SNAPSHOT</span><h2>站点数据</h2></div>
            <VSelect v-model="siteSortKey" :items="siteSortOptions" label="排序方式" prepend-inner-icon="mdi-sort-descending" density="compact" variant="outlined" hide-details class="site-sort-select" />
          </div>
          <div v-if="currentSites.length" class="site-data-list">
            <article v-for="site in sortedCurrentSites" :key="site.site_id || site.site_name" class="site-data-card">
              <header class="site-data-card__header">
                <div class="site-identity"><SiteAvatar :api="api" :site="site" /><div><strong>{{ site.site_name }}</strong><span>{{ site.username || '站点未提供' }} · UID {{ site.userid || '站点未提供' }}</span></div></div>
                <div class="site-account-meta"><VIcon icon="mdi-calendar-outline" size="16" /><span>加入 {{ site.join_at?.slice(0, 10) || '站点未提供' }}</span><VChip size="x-small" color="primary" variant="tonal">{{ site.user_level || '等级未提供' }}</VChip></div>
              </header>
              <div class="site-stat-grid">
                <div><span>累计上传</span><strong class="metric-upload">{{ formatBytes(site.upload) }}</strong></div>
                <div><span>累计下载</span><strong class="metric-download">{{ formatBytes(site.download) }}</strong></div>
                <div><span>今日上传</span><strong class="metric-upload">{{ site.baseline_valid ? formatBytes(site.daily_upload) : '基线不足' }}</strong></div>
                <div><span>今日下载</span><strong class="metric-download">{{ site.baseline_valid ? formatBytes(site.daily_download) : '基线不足' }}</strong></div>
                <div><span>分享率</span><strong>{{ field(site.ratio, 3) }}</strong></div>
                <div><span>魔力</span><strong>{{ bonusValue(site.bonus) }}</strong></div>
                <div><span>预估时魔</span><strong>{{ estimatedBonusHourly(site.estimated_bonus_hourly) }}</strong></div>
                <div><span>做种数</span><strong>{{ formatNumber(site.seeding, 0) }}</strong></div>
                <div><span>做种体积</span><strong>{{ formatBytes(site.seeding_size) }}</strong></div>
              </div>
            </article>
          </div>
          <div v-else class="empty-state compact-empty">MoviePilot 暂无已启用站点数据</div>
        </section>
      </VWindowItem>

      <VWindowItem value="history">
        <section class="history-console">
          <div v-if="historyPeriods.length" class="history-period-strip" role="listbox" aria-label="数据统计周期">
            <VBtnToggle v-model="historyScope" mandatory color="primary" density="compact" variant="outlined" divided class="history-period-scope"><VBtn value="day">日</VBtn><VBtn value="week">周</VBtn><VBtn value="month">月</VBtn></VBtnToggle>
            <button v-for="period in historyPeriods" :key="period.key" type="button" class="history-period-card" :class="{ 'is-selected': selectedHistoryPeriod?.key === period.key }" :aria-selected="selectedHistoryPeriod?.key === period.key" @click="selectHistoryPeriod(period)"><strong>{{ period.label }}</strong><span><b class="metric-upload">↑ {{ period.validCount ? formatBytes(period.upload) : '—' }}</b><b class="metric-download">↓ {{ period.validCount ? formatBytes(period.download) : '—' }}</b></span></button>
          </div>

          <template v-if="selectedHistoryPeriod">
            <header class="history-detail-summary">
              <div class="history-detail-metrics"><div><span>周期上传</span><strong class="metric-upload">{{ selectedHistoryPeriod.validCount ? formatBytes(selectedHistoryPeriod.upload) : '基线不足' }}</strong></div><div><span>周期下载</span><strong class="metric-download">{{ selectedHistoryPeriod.validCount ? formatBytes(selectedHistoryPeriod.download) : '基线不足' }}</strong></div><div><span>有效站点</span><strong>{{ selectedHistoryPeriod.siteCount }}</strong></div><div><span>统计范围</span><strong>{{ historyScope === 'day' ? '00:00–23:59' : `${selectedHistoryPeriod.startDay.slice(5)} 至 ${selectedHistoryPeriod.endDay.slice(5)}` }}</strong></div></div>
            </header>

            <section class="history-workspace">
              <aside class="history-site-sidebar" aria-label="数据统计站点列表">
                <div class="history-site-sidebar__heading"><strong>站点列表</strong><span>共 {{ selectedPeriodSites.length }} 个</span></div>
                <div class="history-site-sidebar__items">
                  <button type="button" class="history-site-option" :class="{ 'is-selected': selectedHistorySiteId === null }" @click="selectHistorySite(null)">
                    <VAvatar :size="34" color="primary" variant="tonal"><VIcon icon="mdi-earth" size="19" /></VAvatar>
                    <span class="history-site-option__body"><strong>全部站点</strong><small><b class="metric-upload">↑ {{ selectedHistoryPeriod.validCount ? formatBytes(selectedHistoryPeriod.upload) : '—' }}</b><b class="metric-download">↓ {{ selectedHistoryPeriod.validCount ? formatBytes(selectedHistoryPeriod.download) : '—' }}</b></small></span>
                  </button>
                  <button v-for="item in selectedPeriodSites" :key="item.site_id || item.site_name" type="button" class="history-site-option" :class="{ 'is-selected': Number(item.site_id) === Number(selectedHistorySiteId) }" @click="selectHistorySite(item)">
                    <SiteAvatar :api="api" :site="item" :size="34" />
                    <span class="history-site-option__body"><strong>{{ item.site_name }}</strong><small><b class="metric-upload">↑ {{ item.valid_count ? formatBytes(item.period_upload) : '—' }}</b><b class="metric-download">↓ {{ item.valid_count ? formatBytes(item.period_download) : '—' }}</b></small></span>
                  </button>
                </div>
              </aside>

              <div class="history-workspace__main">
                <section class="history-trend-panel history-overall-trend">
                  <div class="history-pane-heading history-chart-heading"><div><strong>{{ selectedHistorySite?.site_name || '全部站点' }} · {{ historyScope === 'day' ? '每小时流量' : '按日期流量' }}</strong><span>{{ selectedHistoryPeriod.startDay }}{{ historyScope === 'day' ? ' 00:00–23:59' : ` — ${selectedHistoryPeriod.endDay}` }}</span></div><div class="legend"><i class="legend__upload" />上传 <i class="legend__download" />下载</div></div>
                  <div class="history-line-chart" :class="{ 'is-loading': hourlyLoading }"><canvas :ref="setHistoryChartCanvas" :aria-label="`${selectedHistorySite?.site_name || '全部站点'}上传下载流量曲线图`" /></div>
                  <div v-if="historyScope === 'day' && !hourlyLoading && !hourlyTraffic.baseline_valid" class="history-chart-note">MP 在该日没有足够的相邻采样：小时曲线至少需要同一站点在当天产生 2 次数据刷新</div>
                </section>

                <section class="history-site-panel">
                  <div class="history-pane-heading"><div><strong>{{ selectedHistorySite ? `${selectedHistorySite.site_name} · 历史数据` : '全部站点 · 周期明细' }}</strong><span>{{ selectedHistorySite ? '所选周期内的每日历史数据' : '选择左侧站点可查看该站点历史数据' }}</span></div><VChip v-if="selectedHistorySite" size="small" color="primary" variant="tonal" closable @click:close="selectHistorySite(null)">{{ selectedHistorySite.site_name }}</VChip></div>
                  <div v-if="!selectedHistorySite" class="history-detail-shell"><VTable fixed-header density="compact" class="history-detail-table"><thead><tr><th>站点</th><th>累计数据</th><th>周期增量</th><th>分享率</th><th>魔力</th><th>做种数</th><th>做种体积</th></tr></thead><tbody><tr v-for="item in selectedPeriodSites" :key="`${item.site_id || item.site_name}-${selectedHistoryPeriod.key}`" class="history-site-row" tabindex="0" @click="selectHistorySite(item)" @keydown.enter.prevent="selectHistorySite(item)"><td><div class="site-identity"><SiteAvatar :api="api" :site="item" :size="30" /><strong>{{ item.site_name }}</strong><VIcon icon="mdi-chevron-right" size="17" /></div></td><td><span class="stacked-metric metric-upload">↑ {{ formatBytes(item.upload) }}</span><span class="stacked-metric metric-download">↓ {{ formatBytes(item.download) }}</span></td><td><span class="stacked-metric metric-upload">↑ {{ item.valid_count ? formatBytes(item.period_upload) : '基线不足' }}</span><span class="stacked-metric metric-download">↓ {{ item.valid_count ? formatBytes(item.period_download) : '基线不足' }}</span></td><td>{{ field(item.ratio, 3) }}</td><td>{{ bonusValue(item.bonus) }}</td><td>{{ formatNumber(item.seeding, 0) }} 个</td><td>{{ formatBytes(item.seeding_size) }}</td></tr></tbody></VTable></div>
                  <div v-else class="history-record-shell"><VTable fixed-header density="compact" class="history-record-table"><thead><tr><th>日期</th><th>累计上传</th><th>累计下载</th><th>当日上传</th><th>当日下载</th><th>分享率</th><th>魔力</th><th>做种数</th><th>做种体积</th></tr></thead><tbody><tr v-for="record in selectedHistoryRecords" :key="`${record.site_id}-${record.updated_day}`"><td>{{ record.updated_day || '—' }}</td><td class="metric-upload">{{ formatBytes(record.upload) }}</td><td class="metric-download">{{ formatBytes(record.download) }}</td><td class="metric-upload">{{ record.baseline_valid ? formatBytes(record.daily_upload) : '基线不足' }}</td><td class="metric-download">{{ record.baseline_valid ? formatBytes(record.daily_download) : '基线不足' }}</td><td>{{ field(record.ratio, 3) }}</td><td>{{ bonusValue(record.bonus) }}</td><td>{{ formatNumber(record.seeding, 0) }} 个</td><td>{{ formatBytes(record.seeding_size) }}</td></tr></tbody></VTable></div>
                </section>
              </div>
            </section>
          </template>
          <div v-else class="empty-state"><VIcon icon="mdi-database-search-outline" size="44" /><span>暂无历史数据，请点击顶部“数据刷新”</span></div>
        </section>
      </VWindowItem>

      <VWindowItem value="retirement">
        <section class="section-block twelve-panel">
          <div class="section-heading">
            <div><span class="section-kicker">COLLECTION</span><h2>十二大进度</h2></div>
            <VChip color="primary" variant="tonal" prepend-icon="mdi-trophy-outline">{{ overview.twelve?.joined || 0 }} / {{ overview.twelve?.total || 12 }} · {{ overview.twelve?.percent || 0 }}%</VChip>
          </div>
          <div class="twelve-overflow">
            <div class="twelve-track" role="list" aria-label="十二大站点进度">
              <div class="twelve-track__line"><i :style="{ width: `${overview.twelve?.percent || 0}%` }" /></div>
              <VTooltip v-for="item in twelveItems" :key="item.key" location="top">
                <template #activator="{ props: tooltipProps }">
                  <div v-bind="tooltipProps" class="twelve-node" :class="`twelve-node--${item.state}`" role="listitem" :aria-label="item.state === 'joined' ? item.name : '未解锁节点'">
                    <SiteAvatar v-if="item.state === 'joined' && item.site_id" :api="api" :site="{ site_id: item.site_id, site_name: item.name }" :size="36" />
                    <VAvatar v-else :size="36" color="secondary" variant="tonal"><VIcon :icon="stateMeta(item.state).icon" size="20" /></VAvatar>
                  </div>
                </template>
                <strong>{{ item.state === 'joined' ? item.name : '未解锁' }}</strong>
                <div>{{ item.state === 'joined' && item.join_at ? `加入于 ${item.join_at.slice(0, 10)}` : stateMeta(item.state).label }}</div>
              </VTooltip>
            </div>
          </div>
        </section>
        <section class="section-block">
          <div class="section-heading">
            <div><span class="section-kicker">RETIREMENT</span><h2>养老进度</h2></div>
            <div class="retirement-summary">
              <VChip color="success" variant="tonal">已养老 {{ retirement.retired || 0 }}</VChip>
              <VChip color="warning" variant="tonal">升级中 {{ retirement.upgrading || 0 }}</VChip>
              <VChip color="secondary" variant="tonal">规则缺失 {{ retirement.rule_missing || 0 }}</VChip>
            </div>
          </div>
          <div v-if="selectedRetirementSite" class="retirement-explorer">
            <aside class="retirement-site-list" aria-label="养老进度站点列表">
              <div class="retirement-site-list__heading"><strong>站点列表</strong><span>共 {{ retirement.sites?.length || 0 }} 个站点</span></div>
              <div class="retirement-site-list__items">
                <button
                  v-for="site in retirement.sites || []"
                  :key="retirementSiteKey(site)"
                  type="button"
                  class="retirement-site-option"
                  :class="{ 'retirement-site-option--selected': retirementSiteKey(site) === retirementSiteKey(selectedRetirementSite) }"
                  :aria-pressed="retirementSiteKey(site) === retirementSiteKey(selectedRetirementSite)"
                  @click="selectRetirementSite(site)"
                >
                  <SiteAvatar :api="api" :site="site" :size="42" />
                  <span class="retirement-site-option__body">
                    <span class="retirement-site-option__title"><strong>{{ site.site_name }}</strong><em :class="`status-${site.status}`">{{ retirementMeta(site.status).label }}</em></span>
                    <span>{{ site.current_level || '站点未提供等级' }}</span>
                    <VProgressLinear :model-value="retirementProgressPercent(site)" color="primary" bg-color="surface-variant" height="4" rounded />
                  </span>
                  <small>{{ Math.round(retirementProgressPercent(site)) }}%</small>
                </button>
              </div>
            </aside>

            <article class="retirement-detail">
              <header class="retirement-detail__header">
                <div class="retirement-detail__identity">
                  <SiteAvatar :api="api" :site="selectedRetirementSite" :size="58" />
                  <div><h3>{{ selectedRetirementSite.site_name }}</h3><span>当前等级 <strong>{{ selectedRetirementSite.current_level || '站点未提供' }}</strong></span><span>目标等级 <strong class="target-level">{{ selectedRetirementSite.retirement_level || '规则待补充' }}<template v-if="selectedRetirementSite.retirement_level">（保号）</template></strong></span></div>
                </div>
                <div class="retirement-detail__metrics">
                  <span>上传<strong>{{ formatBytes(selectedRetirementSite.upload) }}</strong></span>
                  <span>下载<strong>{{ formatBytes(selectedRetirementSite.download) }}</strong></span>
                  <span>分享率<strong>{{ field(selectedRetirementSite.ratio, 2) }}</strong></span>
                </div>
              </header>

              <div v-if="retirementRoute(selectedRetirementSite).length" class="retirement-route-rail" aria-label="养老等级进度">
                <div
                  class="retirement-route-rail__track"
                  :style="{
                    '--route-count': retirementRoute(selectedRetirementSite).length,
                    '--route-inset': `${50 / retirementRoute(selectedRetirementSite).length}%`,
                    '--route-span': `${100 - 100 / retirementRoute(selectedRetirementSite).length}%`,
                  }"
                >
                  <div class="retirement-route-rail__line">
                    <VProgressLinear :model-value="retirementProgressPercent(selectedRetirementSite)" color="primary" bg-color="secondary" :bg-opacity="0.3" height="5" rounded />
                  </div>
                  <div class="retirement-route-rail__nodes">
                    <div v-for="level in retirementRoute(selectedRetirementSite)" :key="level.name" :class="{ 'is-reached': level.reached, 'is-current': level.is_current, 'is-retirement': level.is_retirement }">
                      <i class="retirement-route-node__marker" aria-hidden="true" />
                      <span>{{ level.name }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="selectedRetirementSite.route?.length" class="retirement-target-grid">
                <section class="requirement-panel">
                  <div class="requirement-panel__heading"><div><VIcon icon="mdi-target" color="primary" /><span>下一等级</span><strong>{{ selectedRetirementSite.next_level || '已是最高等级' }}</strong></div><VChip :color="retirementMeta(selectedRetirementSite.status).color" size="small" variant="tonal">{{ retirementMeta(selectedRetirementSite.status).label }}</VChip></div>
                  <div v-if="requirementRows(selectedRetirementSite, nextLevelRule(selectedRetirementSite)).length" class="requirement-list">
                    <div v-for="row in requirementRows(selectedRetirementSite, nextLevelRule(selectedRetirementSite))" :key="row.key" class="requirement-row">
                      <VIcon :icon="row.icon" color="secondary" size="22" />
                      <div class="requirement-row__label"><strong>{{ row.label }}</strong><span>目标 {{ row.target }}</span></div>
                      <div class="requirement-row__value"><strong>{{ row.current }}</strong><span :class="{ 'text-success': row.complete, 'text-warning': row.unavailable }">{{ row.detail }}</span></div>
                      <VProgressLinear :model-value="row.progress" :color="row.complete ? 'success' : row.unavailable ? 'warning' : 'primary'" bg-color="surface-variant" height="6" rounded />
                    </div>
                  </div>
                  <div v-else class="compact-empty-state">没有后续等级要求</div>
                </section>

                <section class="retirement-target-panel">
                  <div class="retirement-target-panel__heading"><div><VIcon icon="mdi-shield-check-outline" color="success" /><span>保号目标</span></div><strong>{{ selectedRetirementSite.retirement_level || '规则待补充' }}</strong></div>
                  <div v-if="retirementRule(selectedRetirementSite)" class="retirement-target-panel__rows">
                    <div v-for="row in requirementRows(selectedRetirementSite, retirementRule(selectedRetirementSite))" :key="row.key"><span>{{ row.label }}</span><strong>{{ row.target }}</strong></div>
                    <div class="retirement-target-panel__date"><span>注册时间</span><strong>{{ estimatedLevelDate(retirementRule(selectedRetirementSite)) }}</strong></div>
                  </div>
                  <div v-else class="compact-empty-state">保号规则待补充</div>
                </section>
              </div>

              <section v-if="selectedRetirementSite.route?.length" class="retirement-levels">
                <div class="retirement-levels__heading"><strong>等级路线与要求</strong><span>点击等级查看说明和未达成项目</span></div>
                <div class="retirement-levels__table">
                  <details v-for="level in selectedRetirementSite.route" :key="level.name" class="retirement-level-row" :class="{ 'is-current': level.is_current, 'is-retirement': level.is_retirement }" :open="level.is_current">
                    <summary>
                      <strong>{{ level.name }}</strong>
                      <span>{{ level.min_join_days ? `注册 ${level.min_join_days_strict ? '>' : '≥'} ${durationLabel(level.min_join_days)}` : '注册无限制' }}</span>
                      <span>{{ levelTrafficRequirement(level) }}</span>
                      <span>{{ levelRatioRequirement(level) }}</span>
                      <span>{{ levelPointsRequirement(level) }}</span>
                      <em :class="{ 'text-success': level.reached, 'text-primary': level.is_current }">{{ levelStateLabel(level) }}</em>
                      <VIcon icon="mdi-chevron-down" size="18" />
                    </summary>
                    <div class="retirement-level-row__detail"><span v-if="level.description">{{ level.description }}</span><strong v-if="level.missing?.length">未达成：{{ level.missing.join('；') }}</strong><strong v-else>{{ estimatedLevelDate(level) }}</strong></div>
                  </details>
                </div>
              </section>
              <div v-else class="empty-state compact-empty">该站等级规则尚未确定</div>
            </article>
          </div>
          <div v-if="!retirement.sites?.length" class="empty-state"><VIcon icon="mdi-shield-search-outline" size="42" /><span>MoviePilot 暂无有效站点数据</span></div>
        </section>
      </VWindowItem>

      <VWindowItem value="config">
        <section class="section-block settings-layout">
          <div class="settings-card"><div class="section-heading"><div><span class="section-kicker">GENERAL</span><h2>基础设置</h2></div></div><VSwitch v-model="settingsDraft.enabled" color="primary" label="启用插件" hint="启用后跟随 MP 的站点刷新设置同步已保存数据，并开放插件定时任务" persistent-hint /><VSwitch v-model="settingsDraft.show_sidebar" color="primary" label="在发现栏显示入口" /><VTextField v-model.number="settingsDraft.retention_days" type="number" min="0" max="36500" label="历史保留天数" hint="0 表示永久保留；仅清理插件历史副本" persistent-hint variant="outlined" class="mt-3" /></div>
          <div class="settings-card"><div class="section-heading"><div><span class="section-kicker">NOTIFICATION</span><h2>每日通知</h2></div></div><VSwitch v-model="settingsDraft.notification_enabled" color="primary" label="启用汇总通知" /><VTextField v-model="settingsDraft.notification_cron" label="通知 Cron（五段式）" placeholder="0 9 * * *" hint="分 时 日 月 星期；按服务器时区执行，每个自然日最多通知一次" persistent-hint variant="outlined" /><VCheckbox v-model="settingsDraft.notification_modes" value="today" label="今日数据：仅上传和下载增量" hide-details /><VCheckbox v-model="settingsDraft.notification_modes" value="all" label="所有数据：仅累计上传和累计下载" hide-details /><div class="setting-hint mt-2">Cron 错过后不补发；无数据站点不会通知。</div></div>
          <div class="settings-card settings-card--wide"><div class="section-heading"><div><span class="section-kicker">DATA MANAGEMENT</span><h2>数据管理</h2></div><span class="section-note">导出时可选择站点、日期和隐藏字段</span></div><div class="data-actions"><VBtn variant="tonal" color="primary" prepend-icon="mdi-file-delimited-outline" @click="exportOpen = true">数据导出</VBtn><VBtn variant="tonal" color="primary" prepend-icon="mdi-image-outline" @click="careerOpen = true">PT 生涯</VBtn></div></div>
          <div class="settings-card settings-card--wide settings-actions"><div><strong>数据来源</strong><p>插件只复制 MoviePilot 已保存的站点账户快照，不访问 PT 站点，也不读取下载器。</p></div><VBtn color="primary" size="large" variant="flat" prepend-icon="mdi-content-save-outline" :loading="saving" @click="saveSettings">保存设置</VBtn></div>
        </section>
      </VWindowItem>
    </VWindow>
    <ExportDialog v-model="exportOpen" :api="api" :plugin-base="pluginBase" :sites="historySites" :fields="exportFields" :first-day="overview.first_history_day" :last-day="overview.last_history_day" />
    <CareerExportDialog v-model="careerOpen" :api="api" :overview="overview" />
  </div>
</template>

<style scoped>
.distribution-date-input{max-width:220px}.distribution-date-input :deep(.v-field){border-radius:12px;background:rgba(var(--v-theme-surface),.72)}
.site-sort-select{width:min(100%,220px);flex:0 0 220px}
.history-search-btn{min-height:48px;border-radius:12px;font-weight:700;letter-spacing:.02em}
.workbench-nav{display:flex;align-items:center;justify-content:space-between;gap:18px;border-bottom:1px solid var(--pt-border)}
.workbench-nav .workbench-tabs{min-width:0;flex:1 1 auto;margin:0;border-bottom:0}
.workbench-nav__actions{display:flex;flex:0 0 auto;align-items:center;gap:6px;padding-right:4px}
.data-refresh-btn{border-radius:11px;font-weight:700}
.history-console{min-width:0;margin-top:16px;overflow:hidden;border:1px solid var(--pt-border);border-radius:18px;background:rgba(var(--v-theme-surface),.55)}
.history-period-strip{display:flex;gap:7px;overflow-x:auto;padding:10px 14px;border-bottom:1px solid var(--pt-border);scrollbar-width:thin;scroll-snap-type:x proximity}
.history-period-scope{position:sticky;z-index:2;left:0;flex:0 0 auto;align-self:stretch;background:rgb(var(--v-theme-surface))}.history-period-scope :deep(.v-btn){min-width:42px}
.history-period-card{appearance:none;display:grid;flex:0 0 minmax(150px,1fr);min-width:150px;gap:7px;padding:10px 12px;border:1px solid var(--pt-border);border-radius:11px;background:rgba(var(--v-theme-surface),.34);color:inherit;font:inherit;text-align:left;cursor:pointer;scroll-snap-align:start;transition:background-color .16s ease,border-color .16s ease,box-shadow .16s ease}
.history-period-card:hover,.history-period-card:focus-visible{border-color:rgba(var(--v-theme-primary),.46);background:rgba(var(--v-theme-primary),.07);outline:none}.history-period-card.is-selected{border-color:rgb(var(--v-theme-primary));background:rgba(var(--v-theme-primary),.15);box-shadow:inset 0 -2px rgb(var(--v-theme-primary))}
.history-period-card strong{font-size:.78rem}.history-period-card span{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:.66rem;white-space:nowrap}
.history-pane-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px;border-bottom:1px solid var(--pt-border)}
.history-pane-heading>div{display:flex;min-width:0;flex-direction:column;gap:2px}
.history-pane-heading strong{font-size:.84rem}
.history-pane-heading span{color:rgba(var(--v-theme-on-surface),.52);font-size:.68rem}
.history-detail-summary{display:flex;align-items:center;justify-content:flex-end;gap:22px;padding:13px 18px;border-bottom:1px solid var(--pt-border)}
.history-detail-metrics{display:grid;grid-template-columns:repeat(4,minmax(92px,1fr));gap:20px}.history-detail-metrics>div{display:flex;min-width:0;flex-direction:column;gap:3px}.history-detail-metrics span{color:rgba(var(--v-theme-on-surface),.52);font-size:.66rem}.history-detail-metrics strong{font-size:.8rem;white-space:nowrap}
.history-workspace{display:grid;grid-template-columns:minmax(210px,255px) minmax(0,1fr);height:clamp(610px,calc(100vh - 230px),800px);min-height:0;overflow:hidden}
.history-site-sidebar{display:flex;min-width:0;min-height:0;flex-direction:column;overflow:hidden;padding:12px;border-right:1px solid var(--pt-border);background:rgba(var(--v-theme-surface-variant),.08)}
.history-site-sidebar__heading{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:2px 4px 11px}.history-site-sidebar__heading span{color:rgba(var(--v-theme-on-surface),.52);font-size:.68rem}
.history-site-sidebar__items{display:grid;min-height:0;flex:1 1 auto;align-content:start;gap:6px;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable}
.history-site-option{appearance:none;display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:9px;width:100%;padding:10px;border:1px solid transparent;border-radius:12px;background:transparent;color:inherit;font:inherit;text-align:left;cursor:pointer;transition:background-color .15s ease,border-color .15s ease}
.history-site-option:hover,.history-site-option:focus-visible{border-color:rgba(var(--v-theme-primary),.34);background:rgba(var(--v-theme-primary),.07);outline:none}.history-site-option.is-selected{border-color:rgba(var(--v-theme-primary),.5);background:rgba(var(--v-theme-primary),.14);box-shadow:inset 3px 0 rgb(var(--v-theme-primary))}
.history-site-option__body{display:grid;min-width:0;gap:4px}.history-site-option__body>strong{overflow:hidden;font-size:.76rem;text-overflow:ellipsis;white-space:nowrap}.history-site-option__body>small{display:flex;min-width:0;justify-content:space-between;gap:7px;font-size:.62rem}.history-site-option__body b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.history-workspace__main{min-width:0;min-height:0;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable}
.history-trend-panel{border-bottom:1px solid var(--pt-border);background:rgba(var(--v-theme-surface-variant),.035)}
.history-trend-panel .history-pane-heading,.history-site-panel .history-pane-heading{border-bottom:0;padding-bottom:7px}
.history-chart-heading{align-items:flex-end}.history-line-chart{position:relative;height:260px;margin:0 14px 10px}.history-line-chart.is-loading{opacity:.48}.history-chart-note{padding:0 16px 10px;color:rgb(var(--v-theme-warning));font-size:.68rem}
.history-site-panel{min-width:0;padding-bottom:14px}
.history-site-panel .history-detail-shell{max-height:460px;overflow-x:hidden;overflow-y:auto;margin:0 14px;padding:0;border:1px solid var(--pt-border);border-radius:12px;scrollbar-gutter:stable}
.history-site-panel .history-detail-table{width:100%;min-width:0;table-layout:fixed}
.history-detail-table th:nth-child(1){width:18%}.history-detail-table th:nth-child(2),.history-detail-table th:nth-child(3){width:18%}.history-detail-table th:nth-child(4){width:11%}.history-detail-table th:nth-child(5){width:13%}.history-detail-table th:nth-child(6){width:10%}.history-detail-table th:nth-child(7){width:12%}
.history-site-row{cursor:pointer;transition:background-color .15s ease}.history-site-row:hover,.history-site-row:focus{background:rgba(var(--v-theme-primary),.07);outline:none}
.history-site-row .site-identity{min-width:0}.history-site-row .site-identity strong{min-width:0;overflow:hidden;text-overflow:ellipsis}.history-site-row .site-identity .v-icon{margin-left:auto;color:rgba(var(--v-theme-on-surface),.5)}
.history-record-shell{max-height:460px;overflow-x:hidden;overflow-y:auto;margin:0 14px 14px;border:1px solid var(--pt-border);border-radius:10px;background:rgba(var(--v-theme-surface),.42);scrollbar-gutter:stable}.history-record-table{width:100%;min-width:0;table-layout:fixed;background:transparent}.history-record-table th{color:rgba(var(--v-theme-on-surface),.55)!important;font-size:.62rem;white-space:nowrap}.history-record-table td{overflow:hidden;font-size:.66rem;text-overflow:ellipsis;white-space:nowrap}
.stacked-metric{display:block;overflow:hidden;font-size:.7rem;line-height:1.45;text-overflow:ellipsis;white-space:nowrap}
.site-data-list{display:grid;gap:12px}
.site-data-card{min-width:0;padding:16px;border:1px solid var(--pt-border);border-radius:16px;background:rgba(var(--v-theme-surface-variant),.12)}
.site-data-card__header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding-bottom:12px;border-bottom:1px solid var(--pt-border)}
.site-data-card__header .site-identity>div{display:flex;flex-direction:column;min-width:0}
.site-data-card__header .site-identity span,.site-account-meta{color:rgba(var(--v-theme-on-surface),.56);font-size:.72rem}
.site-account-meta{display:flex;flex-wrap:wrap;align-items:center;justify-content:flex-end;gap:7px}
.site-stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:8px;margin-top:12px}
.site-stat-grid>div{display:flex;min-width:0;flex-direction:column;gap:4px;padding:10px 12px;border-radius:10px;background:rgba(var(--v-theme-surface),.54)}
.site-stat-grid span{color:rgba(var(--v-theme-on-surface),.52);font-size:.68rem}
.site-stat-grid strong{overflow-wrap:anywhere;font-size:.82rem}
.retirement-explorer{display:grid;grid-template-columns:minmax(240px,300px) minmax(0,1fr);height:clamp(560px,calc(100vh - 240px),760px);min-height:0;overflow:hidden;border:1px solid var(--pt-border);border-radius:18px;background:rgba(var(--v-theme-surface),.44)}
.retirement-site-list{display:flex;min-width:0;min-height:0;flex-direction:column;overflow:hidden;padding:14px;border-right:1px solid var(--pt-border);background:rgba(var(--v-theme-surface-variant),.1)}
.retirement-site-list__heading{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:2px 4px 12px}
.retirement-site-list__heading span{color:rgba(var(--v-theme-on-surface),.52);font-size:.7rem}
.retirement-site-list__items{display:grid;min-height:0;flex:1 1 auto;align-content:start;gap:5px;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable}
.retirement-site-option{appearance:none;display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:10px;width:100%;padding:11px 10px;border:1px solid transparent;border-radius:12px;background:transparent;color:inherit;font:inherit;text-align:left;cursor:pointer;transition:background-color .16s ease,border-color .16s ease}
.retirement-site-option:hover,.retirement-site-option:focus-visible{border-color:rgba(var(--v-theme-primary),.34);background:rgba(var(--v-theme-primary),.08);outline:none}
.retirement-site-option--selected{border-color:rgba(var(--v-theme-primary),.46);background:rgba(var(--v-theme-primary),.12)}
.retirement-site-option__body{display:grid;min-width:0;gap:4px}
.retirement-site-option__body>span:nth-child(2){overflow:hidden;color:rgba(var(--v-theme-on-surface),.58);font-size:.7rem;text-overflow:ellipsis;white-space:nowrap}
.retirement-site-option__title{display:flex;min-width:0;align-items:center;justify-content:space-between;gap:7px}
.retirement-site-option__title strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.retirement-site-option__title em{flex:0 0 auto;font-size:.66rem;font-style:normal;font-weight:700}
.retirement-site-option>small{color:rgba(var(--v-theme-on-surface),.52);font-size:.68rem;font-weight:700}
.status-retired{color:rgb(var(--v-theme-success))}.status-upgrading{color:rgb(var(--v-theme-primary))}.status-rule_missing{color:rgb(var(--v-theme-warning))}
.retirement-detail{min-width:0;min-height:0;overflow-y:auto;overscroll-behavior:contain;padding:20px;scrollbar-gutter:stable}
.retirement-detail__header{display:flex;align-items:center;justify-content:space-between;gap:24px;padding-bottom:18px;border-bottom:1px solid var(--pt-border)}
.retirement-detail__identity{display:flex;min-width:0;align-items:center;gap:14px}
.retirement-detail__identity>div{display:flex;min-width:0;flex-direction:column;gap:3px}
.retirement-detail__identity h3{margin:0;font-size:1.2rem}
.retirement-detail__identity span{color:rgba(var(--v-theme-on-surface),.58);font-size:.72rem}
.retirement-detail__identity span strong{color:rgba(var(--v-theme-on-surface),.86)}
.retirement-detail__identity .target-level{color:rgb(var(--v-theme-success))}
.retirement-detail__metrics{display:flex;flex:0 0 auto;align-items:center;gap:22px}
.retirement-detail__metrics span{display:flex;flex-direction:column;gap:3px;color:rgba(var(--v-theme-on-surface),.52);font-size:.68rem}
.retirement-detail__metrics strong{color:rgba(var(--v-theme-on-surface),.9);font-size:.86rem}
.retirement-route-rail{overflow-x:auto;padding:28px 12px 12px}
.retirement-route-rail__track{position:relative;min-width:620px}
.retirement-route-rail__line{position:absolute;z-index:0;top:5.5px;left:var(--route-inset);width:var(--route-span)}
.retirement-route-rail__nodes{position:relative;z-index:1;display:grid;grid-template-columns:repeat(var(--route-count),minmax(80px,1fr));align-items:start}
.retirement-route-rail__nodes>div{display:flex;min-width:0;flex-direction:column;align-items:center;gap:5px;text-align:center}
.retirement-route-node__marker{display:block;width:16px;height:16px;border:3px solid rgba(var(--v-theme-on-surface),.28);border-radius:50%;background:rgb(var(--v-theme-surface));box-shadow:0 0 0 4px rgb(var(--v-theme-surface))}
.retirement-route-rail__nodes .is-reached .retirement-route-node__marker{border-color:rgb(var(--v-theme-primary));background:rgb(var(--v-theme-primary))}
.retirement-route-rail__nodes .is-current .retirement-route-node__marker{box-shadow:0 0 0 4px rgb(var(--v-theme-surface)),0 0 0 7px rgba(var(--v-theme-primary),.18)}
.retirement-route-rail__nodes .is-retirement .retirement-route-node__marker{border-color:rgb(var(--v-theme-success));background:rgb(var(--v-theme-success))}
.retirement-route-rail__nodes span{max-width:100%;overflow:hidden;color:rgba(var(--v-theme-on-surface),.55);font-size:.66rem;text-overflow:ellipsis;white-space:nowrap}
.retirement-route-rail__nodes .is-current span{color:rgb(var(--v-theme-primary));font-weight:800}
.retirement-route-rail__nodes .is-retirement span{color:rgb(var(--v-theme-success));font-weight:800}
.retirement-target-grid{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(240px,.8fr);gap:14px;margin-top:16px}
.requirement-panel,.retirement-target-panel,.retirement-levels{min-width:0;border:1px solid var(--pt-border);border-radius:14px;background:rgba(var(--v-theme-surface-variant),.1)}
.requirement-panel,.retirement-target-panel{padding:15px}
.requirement-panel__heading,.retirement-target-panel__heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}
.requirement-panel__heading>div,.retirement-target-panel__heading>div{display:flex;align-items:center;gap:7px}
.requirement-panel__heading span,.retirement-target-panel__heading span{color:rgba(var(--v-theme-on-surface),.56);font-size:.72rem}
.requirement-panel__heading strong{margin-left:3px}
.requirement-list{display:grid}
.requirement-row{display:grid;grid-template-columns:auto minmax(100px,.8fr) minmax(130px,1fr) minmax(105px,.85fr);align-items:center;gap:10px;padding:10px 0;border-top:1px solid var(--pt-border)}
.requirement-row__label,.requirement-row__value{display:flex;min-width:0;flex-direction:column;gap:2px}
.requirement-row__label span,.requirement-row__value span{color:rgba(var(--v-theme-on-surface),.54);font-size:.66rem}
.requirement-row__label strong,.requirement-row__value strong{font-size:.76rem}
.retirement-target-panel__heading>strong{color:rgb(var(--v-theme-success))}
.retirement-target-panel__rows{display:grid;gap:0}
.retirement-target-panel__rows>div{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 0;border-top:1px solid var(--pt-border);font-size:.74rem}
.retirement-target-panel__rows span{color:rgba(var(--v-theme-on-surface),.56)}
.retirement-target-panel__date strong{color:rgb(var(--v-theme-success))}
.compact-empty-state{display:grid;min-height:88px;place-items:center;color:rgba(var(--v-theme-on-surface),.5);font-size:.76rem}
.retirement-levels{margin-top:14px;overflow:hidden}
.retirement-levels__heading{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 15px}
.retirement-levels__heading span{color:rgba(var(--v-theme-on-surface),.5);font-size:.68rem}
.retirement-levels__table{overflow-x:auto}
.retirement-level-row{min-width:800px;border-top:1px solid var(--pt-border)}
.retirement-level-row summary{display:grid;grid-template-columns:minmax(120px,1fr) repeat(4,minmax(105px,1fr)) auto auto;align-items:center;gap:12px;padding:12px 15px;cursor:pointer;list-style:none}
.retirement-level-row summary::-webkit-details-marker{display:none}
.retirement-level-row summary span{color:rgba(var(--v-theme-on-surface),.56);font-size:.71rem}
.retirement-level-row summary em{font-size:.7rem;font-style:normal;font-weight:800}
.retirement-level-row.is-current{background:rgba(var(--v-theme-primary),.07)}
.retirement-level-row.is-retirement{box-shadow:inset 3px 0 rgb(var(--v-theme-success))}
.retirement-level-row__detail{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;padding:0 15px 13px 147px;color:rgba(var(--v-theme-on-surface),.66);font-size:.72rem}
.retirement-level-row__detail strong{color:rgb(var(--v-theme-warning))}
.pt-workbench{--pt-border:rgba(var(--v-border-color),var(--v-border-opacity));min-width:0;padding:4px}.data-actions,.retirement-summary{display:flex;flex-wrap:wrap;gap:9px}.section-block{margin-top:16px;padding:20px;border:1px solid var(--pt-border);border-radius:20px;background:rgba(var(--v-theme-surface),.7)}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}.section-heading h2{margin:2px 0 0;font-size:1.18rem}.section-kicker{color:rgb(var(--v-theme-primary));font-size:.72rem;font-weight:800;letter-spacing:.12em}.section-note,.setting-hint,.row-label{color:rgba(var(--v-theme-on-surface),.56);font-size:.76rem}.metric-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}.distribution-panel,.twelve-panel{background:linear-gradient(135deg,rgba(var(--v-theme-primary),.07),rgba(var(--v-theme-surface),.72))}.distribution-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.distribution-card{min-width:0;padding:18px;border:1px solid var(--pt-border);border-radius:17px;background:rgba(var(--v-theme-surface),.55)}.distribution-card__header{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:14px}.distribution-card__header :deep(.v-input){max-width:190px}.pie-layout{display:grid;grid-template-columns:minmax(150px,40%) minmax(0,1fr);gap:20px;align-items:center}.pie{display:grid;place-items:center;width:min(100%,220px);margin:auto;aspect-ratio:1;border-radius:50%;box-shadow:0 12px 32px rgba(0,0,0,.15)}.pie__hole{display:flex;flex-direction:column;align-items:center;justify-content:center;width:66%;aspect-ratio:1;border-radius:50%;background:rgb(var(--v-theme-surface));text-align:center}.pie__hole span{color:rgba(var(--v-theme-on-surface),.58);font-size:.68rem}.pie__hole strong{margin-top:5px;font-size:1rem}.pie-legend{max-height:250px;overflow-y:auto}.pie-legend>div{display:grid;grid-template-columns:9px minmax(80px,1fr) auto auto;gap:8px;align-items:center;padding:6px 2px;font-size:.74rem}.pie-legend i{width:8px;height:8px;border-radius:50%}.pie-legend strong{font-size:.72rem}.pie-legend em{color:rgba(var(--v-theme-on-surface),.5);font-style:normal}.table-shell,.twelve-overflow{overflow-x:auto;border:1px solid var(--pt-border);border-radius:14px}.site-table{min-width:1450px;background:transparent}.history-detail-shell{overflow-x:auto}.history-detail-table{min-width:1050px}.site-table th{color:rgba(var(--v-theme-on-surface),.55)!important;font-size:.7rem;letter-spacing:.04em;white-space:nowrap}.site-table td{white-space:nowrap}.site-identity{display:flex;align-items:center;gap:10px}.cell-sub{display:block;max-width:220px;overflow:hidden;color:rgba(var(--v-theme-on-surface),.52);font-size:.68rem;text-overflow:ellipsis;white-space:nowrap}.metric-upload{color:rgb(var(--v-theme-success));font-weight:650}.metric-download{color:rgb(var(--v-theme-error));font-weight:650}.empty-cell{height:140px!important;text-align:center;color:rgba(var(--v-theme-on-surface),.52)}.legend{display:flex;align-items:center;gap:7px;font-size:.75rem;color:rgba(var(--v-theme-on-surface),.62)}.legend i{width:9px;height:9px;border-radius:2px}.legend__upload{background:rgb(var(--v-theme-success))}.legend__download{margin-left:8px;background:rgb(var(--v-theme-error))}.bar-chart{display:flex;align-items:stretch;gap:5px;height:250px;overflow-x:auto;padding:10px 3px 0;border-bottom:1px solid var(--pt-border)}.bar-column{display:flex;flex:1 0 28px;flex-direction:column;min-width:28px}.bar-column__bars{display:flex;flex:1;align-items:flex-end;justify-content:center;gap:2px}.bar{display:block;width:7px;border-radius:5px 5px 1px 1px}.bar--upload{background:rgb(var(--v-theme-success))}.bar--download{background:rgb(var(--v-theme-error))}.empty-state{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;min-height:180px;color:rgba(var(--v-theme-on-surface),.54)}.compact-empty{min-height:120px}.twelve-track{position:relative;display:grid;grid-template-columns:repeat(12,minmax(54px,1fr));min-width:760px;padding:20px 4px 4px}.twelve-track__line{position:absolute;z-index:0;top:38px;left:4.2%;right:4.2%;height:5px;overflow:hidden;border-radius:999px;background:rgba(var(--v-theme-on-surface),.12)}.twelve-track__line i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,rgb(var(--v-theme-primary)),rgb(var(--v-theme-success)))}.twelve-node{z-index:1;display:flex;flex-direction:column;align-items:center;gap:8px;min-width:0;text-align:center}.twelve-node span{max-width:100%;overflow:hidden;font-size:.72rem;text-overflow:ellipsis;white-space:nowrap}.twelve-node--missing,.twelve-node--waiting{opacity:.66}.settings-layout{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;border:0;padding:0;background:transparent}.settings-card{padding:20px;border:1px solid var(--pt-border);border-radius:18px;background:rgba(var(--v-theme-surface),.76)}.settings-card--wide{grid-column:1/-1}.settings-actions{display:flex;align-items:center;justify-content:space-between;gap:20px}.settings-actions p{margin:4px 0 0;color:rgba(var(--v-theme-on-surface),.56)}
@media(max-width:1280px){.metric-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.retirement-target-grid{grid-template-columns:1fr}}
@media(max-width:960px){.workbench-nav{align-items:stretch;flex-direction:column;gap:5px}.workbench-nav__actions{align-self:flex-end;padding-bottom:10px}.history-workspace{grid-template-columns:1fr;height:auto;overflow:visible}.history-site-sidebar{overflow:visible;border-right:0;border-bottom:1px solid var(--pt-border)}.history-site-sidebar__items{display:flex;max-height:none;overflow-x:auto;overflow-y:hidden;scrollbar-gutter:auto}.history-site-option{width:210px;flex:0 0 210px}.history-workspace__main{overflow:visible;scrollbar-gutter:auto}.history-record-shell{overflow-x:auto}.history-record-table{min-width:900px;table-layout:auto}.distribution-grid{grid-template-columns:1fr}.retirement-explorer{grid-template-columns:1fr;height:auto;min-height:0;overflow:visible}.retirement-site-list{overflow:visible;border-right:0;border-bottom:1px solid var(--pt-border)}.retirement-site-list__items{display:flex;max-height:none;overflow-x:auto;overflow-y:hidden;scrollbar-gutter:auto}.retirement-site-option{width:245px;flex:0 0 245px}.retirement-detail{overflow:visible;scrollbar-gutter:auto}}
@media(max-width:720px){.workbench-nav__actions{align-self:stretch}.data-refresh-btn{flex:1}.section-block{padding:14px}.metric-grid,.settings-layout{grid-template-columns:1fr}.settings-card--wide{grid-column:auto}.settings-actions{align-items:stretch;flex-direction:column}.section-heading,.distribution-heading{align-items:flex-start;flex-direction:column}.pie-layout{grid-template-columns:1fr}.pie{width:180px}.history-detail-summary{align-items:flex-start;flex-direction:column}.history-detail-metrics{width:100%;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.history-period-card{min-width:142px}.history-line-chart{height:220px}.history-site-panel .history-detail-shell{overflow-x:auto}.history-site-panel .history-detail-table{min-width:720px}}
@media(max-width:720px){.site-sort-select{width:100%;flex:0 0 auto}.site-data-card{padding:12px}.site-data-card__header,.site-account-meta{align-items:flex-start;flex-direction:column}.site-stat-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.retirement-detail{padding:14px}.retirement-detail__header{align-items:flex-start;flex-direction:column}.retirement-detail__metrics{width:100%;justify-content:space-between;gap:10px}.retirement-route-rail{margin-right:-14px;margin-left:-14px;padding-right:14px;padding-left:14px}.requirement-row{grid-template-columns:auto minmax(0,1fr) minmax(0,1fr)}.requirement-row :deep(.v-progress-linear){grid-column:2/-1}.retirement-levels__heading{align-items:flex-start;flex-direction:column}.retirement-level-row__detail{padding-left:15px}}
</style>
