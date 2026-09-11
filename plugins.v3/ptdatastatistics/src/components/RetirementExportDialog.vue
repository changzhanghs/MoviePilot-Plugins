<script setup>
import { computed, ref, watch } from 'vue'
import { formatBytes, formatNumber, getSiteIcon, siteColors } from '../utils'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  api: { type: Object, default: () => ({}) },
  overview: { type: Object, default: () => ({ retirement: { sites: [] } }) },
})

const emit = defineEmits(['update:modelValue'])
const selectedSiteKeys = ref([])
const generating = ref(false)

const opened = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})
const sites = computed(() => props.overview.retirement?.sites || [])
const siteItems = computed(() => sites.value.map(site => ({
  title: site.site_name,
  value: siteKey(site),
})))
const selectedSites = computed(() => sites.value.filter(site => selectedSiteKeys.value.includes(siteKey(site))))

watch(
  () => props.modelValue,
  value => {
    if (value) selectedSiteKeys.value = sites.value.map(siteKey)
  },
)

function siteKey(site) {
  return String(site?.site_id || site?.site_name || '')
}
function roundedRect(ctx, x, y, width, height, radius, fill, stroke = '') {
  ctx.beginPath()
  ctx.roundRect(x, y, width, height, radius)
  ctx.fillStyle = fill
  ctx.fill()
  if (stroke) {
    ctx.strokeStyle = stroke
    ctx.stroke()
  }
}
function drawText(ctx, text, x, y, options = {}) {
  ctx.fillStyle = options.color || '#f6f1ff'
  ctx.font = `${options.weight || 500} ${options.size || 24}px system-ui, "Microsoft YaHei", sans-serif`
  ctx.textAlign = options.align || 'left'
  ctx.textBaseline = options.baseline || 'alphabetic'
  const maxWidth = options.maxWidth || 1200
  let value = String(text ?? '')
  while (ctx.measureText(value).width > maxWidth && value.length > 2) value = `${value.slice(0, -2)}…`
  ctx.fillText(value, x, y)
}
function loadImage(source) {
  return new Promise(resolve => {
    if (!source || !source.startsWith('data:')) return resolve(null)
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => resolve(null)
    image.src = source
  })
}
function siteStatus(site) {
  if (site.status === 'retired') return { label: '已养老', color: '#86efac' }
  if (site.status === 'upgrading') return { label: '升级中', color: '#c4b5fd' }
  return { label: '规则缺失', color: '#fbbf24' }
}
function siteProgress(site) {
  const route = site.route || []
  const current = route.findIndex(level => level.is_current)
  const target = route.findIndex(level => level.is_retirement)
  if (site.status === 'retired') return 100
  if (current < 0 || target <= 0) return 0
  return Math.max(0, Math.min(100, Math.round(current * 100 / target)))
}
function siteCardHeight(site) {
  const routeRows = Math.max(1, Math.ceil((site.route || []).length / 8))
  return 170 + routeRows * 112
}
function drawSiteIcon(ctx, icon, site, index, x, y) {
  ctx.beginPath()
  ctx.arc(x, y, 27, 0, Math.PI * 2)
  ctx.fillStyle = `${siteColors[index % siteColors.length]}33`
  ctx.fill()
  if (icon) {
    ctx.save()
    ctx.beginPath()
    ctx.arc(x, y, 24, 0, Math.PI * 2)
    ctx.clip()
    ctx.drawImage(icon, x - 24, y - 24, 48, 48)
    ctx.restore()
  } else {
    drawText(ctx, String(site.site_name || '?').slice(0, 1), x, y + 8, {
      size: 27, weight: 800, align: 'center', color: siteColors[index % siteColors.length],
    })
  }
}
function drawRoute(ctx, site, x, y, width) {
  const route = site.route || []
  if (!route.length) {
    drawText(ctx, '该站尚无可用等级规则', x, y + 42, { size: 22, color: '#fbbf24' })
    return
  }
  const perRow = 8
  route.forEach((level, index) => {
    const row = Math.floor(index / perRow)
    const column = index % perRow
    const count = Math.min(perRow, route.length - row * perRow)
    const cellWidth = width / count
    const centerX = x + cellWidth * (column + .5)
    const centerY = y + row * 112 + 32
    if (column < count - 1) {
      ctx.fillStyle = level.reached ? '#8b5cf6' : 'rgba(255,255,255,.16)'
      ctx.fillRect(centerX, centerY - 2, cellWidth, 4)
    }
    const color = level.is_retirement ? '#65d20a' : level.reached ? '#8b5cf6' : '#777383'
    ctx.beginPath()
    ctx.arc(centerX, centerY, 21, 0, Math.PI * 2)
    ctx.fillStyle = level.is_current ? '#4c1d95' : '#171522'
    ctx.fill()
    ctx.lineWidth = 5
    ctx.strokeStyle = color
    ctx.stroke()
    drawText(ctx, index + 1, centerX, centerY + 7, { size: 18, weight: 800, align: 'center' })
    drawText(ctx, level.name, centerX, centerY + 58, {
      size: 17, weight: 700, align: 'center', color, maxWidth: cellWidth - 10,
    })
    const state = level.is_current ? '当前' : level.is_retirement ? '保号目标' : level.reached ? '已达成' : '待达成'
    drawText(ctx, state, centerX, centerY + 84, { size: 14, align: 'center', color: '#aaa3b8' })
  })
}

async function generateImage() {
  if (!selectedSites.value.length) return
  generating.value = true
  try {
    const logicalWidth = 1440
    const margin = 64
    const gap = 22
    const logicalHeight = 210 + selectedSites.value.reduce((sum, site) => sum + siteCardHeight(site) + gap, 0) + 42
    const scale = Math.min(2, 30000 / logicalHeight)
    const canvas = document.createElement('canvas')
    canvas.width = logicalWidth * scale
    canvas.height = logicalHeight * scale
    const ctx = canvas.getContext('2d')
    ctx.scale(scale, scale)

    const gradient = ctx.createLinearGradient(0, 0, logicalWidth, logicalHeight)
    gradient.addColorStop(0, '#151124')
    gradient.addColorStop(.5, '#0d1627')
    gradient.addColorStop(1, '#111827')
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, logicalWidth, logicalHeight)
    const glow = ctx.createRadialGradient(1160, 100, 0, 1160, 100, 620)
    glow.addColorStop(0, 'rgba(124,58,237,.25)')
    glow.addColorStop(1, 'rgba(124,58,237,0)')
    ctx.fillStyle = glow
    ctx.fillRect(0, 0, logicalWidth, 650)

    drawText(ctx, '养老进度', margin, 94, { size: 52, weight: 800 })
    drawText(ctx, 'MoviePilot · PT数据统计', margin, 140, { size: 23, color: '#a9a2ba' })
    drawText(ctx, `更新于 ${props.overview.generated_at?.replace('T', ' ') || ''}`, logicalWidth - margin, 96, {
      size: 20, color: '#a9a2ba', align: 'right',
    })
    drawText(ctx, `${selectedSites.value.length} 个站点`, logicalWidth - margin, 138, {
      size: 24, weight: 700, color: '#86efac', align: 'right',
    })

    const iconSources = await Promise.all(selectedSites.value.map(site => getSiteIcon(props.api, site.site_id)))
    const icons = await Promise.all(iconSources.map(loadImage))
    let y = 176
    selectedSites.value.forEach((site, index) => {
      const height = siteCardHeight(site)
      const status = siteStatus(site)
      roundedRect(ctx, margin, y, logicalWidth - margin * 2, height, 24, 'rgba(255,255,255,.055)', 'rgba(255,255,255,.11)')
      drawSiteIcon(ctx, icons[index], site, index, margin + 48, y + 52)
      drawText(ctx, site.site_name, margin + 90, y + 48, { size: 29, weight: 780, maxWidth: 330 })
      drawText(ctx, `${status.label} · ${siteProgress(site)}%`, margin + 90, y + 78, { size: 18, color: status.color })
      const metrics = [
        ['当前等级', site.current_level || '站点未提供'],
        ['保号目标', site.retirement_level || '规则缺失'],
        ['上传', formatBytes(site.upload)],
        ['下载', formatBytes(site.download)],
        ['分享率', formatNumber(site.ratio, 2)],
        ['做种积分', formatNumber(site.seeding_points, 0)],
      ]
      metrics.forEach(([label, value], metricIndex) => {
        const metricX = margin + 450 + metricIndex * 135
        drawText(ctx, label, metricX, y + 38, { size: 15, color: '#8f899d' })
        drawText(ctx, value, metricX, y + 70, { size: 19, weight: 680, maxWidth: 122 })
      })
      ctx.fillStyle = 'rgba(255,255,255,.1)'
      ctx.fillRect(margin + 24, y + 104, logicalWidth - margin * 2 - 48, 1)
      drawRoute(ctx, site, margin + 24, y + 122, logicalWidth - margin * 2 - 48)
      y += height + gap
    })

    await new Promise(resolve => {
      canvas.toBlob(blob => {
        if (!blob) return resolve()
        const url = URL.createObjectURL(blob)
        const anchor = document.createElement('a')
        anchor.href = url
        anchor.download = `养老进度-${props.overview.server_date || 'latest'}.png`
        document.body.appendChild(anchor)
        anchor.click()
        anchor.remove()
        URL.revokeObjectURL(url)
        resolve()
      }, 'image/png')
    })
  } finally {
    generating.value = false
  }
}
</script>

<template>
  <VDialog v-model="opened" max-width="820" scrollable>
    <VCard rounded="xl">
      <VCardTitle class="d-flex align-center ga-2 pa-5">
        <VIcon icon="mdi-shield-star-outline" color="primary" />
        导出养老进度
      </VCardTitle>
      <VDivider />
      <VCardText class="pa-5">
        <VSelect v-model="selectedSiteKeys" :items="siteItems" label="图片包含的站点" multiple chips closable-chips variant="outlined" />
        <VAlert type="info" variant="tonal" class="mt-3">
          图片包含当前等级、保号目标、账户关键数据和完整等级路线；站点越多，高清 PNG 会自动增长高度。
        </VAlert>
      </VCardText>
      <VDivider />
      <VCardActions class="pa-4 justify-end">
        <VBtn variant="text" @click="opened = false">取消</VBtn>
        <VBtn color="primary" variant="flat" prepend-icon="mdi-download" :loading="generating" :disabled="!selectedSites.length" @click="generateImage">生成高清 PNG</VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>
