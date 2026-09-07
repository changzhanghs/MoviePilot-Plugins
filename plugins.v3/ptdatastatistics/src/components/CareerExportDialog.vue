<script setup>
import { computed, ref, watch } from 'vue'
import { formatBytes, formatNumber, getSiteIcon, siteColors } from '../utils'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  api: { type: Object, default: () => ({}) },
  overview: { type: Object, default: () => ({ summary: {}, sites: [] }) },
})

const emit = defineEmits(['update:modelValue'])
const selectedSiteIds = ref([])
const visibleFields = ref([])
const generating = ref(false)

const opened = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})

const summaryFields = [
  { key: 'total_upload', label: '总上传' },
  { key: 'total_download', label: '总下载' },
  { key: 'overall_ratio', label: '总分享率' },
  { key: 'total_seeding', label: '总做种数' },
  { key: 'total_seeding_size', label: '总做种体积' },
  { key: 'valid_sites', label: '有效站点数' },
  { key: 'earliest_join_at', label: '最早加入时间' },
  { key: 'career_days', label: 'PT 生涯天数' },
  { key: 'average_upload', label: '平均上传' },
  { key: 'average_download', label: '平均下载' },
  { key: 'top_upload_site', label: '上传领先站点' },
  { key: 'top_download_site', label: '下载领先站点' },
]

const siteFields = [
  { key: 'site_name', label: '站点名称', header: true },
  { key: 'updated_day', label: '数据日期', header: true },
  { key: 'username', label: '用户名' },
  { key: 'userid', label: 'UID' },
  { key: 'join_at', label: '加入时间' },
  { key: 'user_level', label: '用户等级' },
  { key: 'upload', label: '累计上传' },
  { key: 'download', label: '累计下载' },
  { key: 'ratio', label: '分享率' },
  { key: 'bonus', label: '魔力' },
  { key: 'seeding', label: '做种数量' },
  { key: 'seeding_size', label: '做种体积' },
]

const selectedSites = computed(() =>
  (props.overview.sites || []).filter(site => selectedSiteIds.value.includes(site.site_id)),
)

watch(
  () => props.modelValue,
  value => {
    if (!value) return
    selectedSiteIds.value = (props.overview.sites || []).map(site => site.site_id).filter(Boolean)
    visibleFields.value = [...summaryFields, ...siteFields].map(field => field.key)
  },
)

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
  ctx.font = `${options.weight || 500} ${options.size || 28}px system-ui, "Microsoft YaHei", sans-serif`
  ctx.textAlign = options.align || 'left'
  ctx.textBaseline = options.baseline || 'alphabetic'
  const maxWidth = options.maxWidth || 1200
  let value = String(text ?? '')
  while (ctx.measureText(value).width > maxWidth && value.length > 2) value = `${value.slice(0, -2)}…`
  ctx.fillText(value, x, y)
}

function summaryValue(key, summary) {
  if (['total_upload', 'total_download', 'total_seeding_size', 'average_upload', 'average_download'].includes(key)) return formatBytes(summary[key])
  if (key === 'overall_ratio') return formatNumber(summary[key], 3)
  if (key === 'career_days') return summary[key] ? `${summary[key]} 天` : '站点未提供'
  if (key === 'earliest_join_at') return summary[key] || '站点未提供'
  if (['top_upload_site', 'top_download_site'].includes(key)) return summary[key] || '站点未提供'
  return formatNumber(summary[key], 0)
}

function siteValue(key, site) {
  if (['upload', 'download', 'seeding_size'].includes(key)) return formatBytes(site[key])
  if (['ratio', 'bonus'].includes(key)) return formatNumber(site[key], key === 'ratio' ? 3 : 2)
  return site[key] || (key === 'seeding' ? '0' : '站点未提供')
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

async function generateImage() {
  if (!selectedSites.value.length) return
  generating.value = true
  try {
    const chosenSummary = summaryFields.filter(field => visibleFields.value.includes(field.key))
    const chosenSite = siteFields.filter(field => !field.header && visibleFields.value.includes(field.key))
    const logicalWidth = 1440
    const margin = 64
    const summaryRows = Math.ceil(chosenSummary.length / 4)
    const summaryHeight = summaryRows ? summaryRows * 142 + 70 : 20
    const fieldRows = Math.ceil(chosenSite.length / 4)
    const siteCardHeight = 132 + fieldRows * 86
    const logicalHeight = 250 + summaryHeight + selectedSites.value.length * (siteCardHeight + 22) + 80
    const scale = Math.min(2, 30000 / logicalHeight)
    const canvas = document.createElement('canvas')
    canvas.width = logicalWidth * scale
    canvas.height = logicalHeight * scale
    const ctx = canvas.getContext('2d')
    ctx.scale(scale, scale)

    const gradient = ctx.createLinearGradient(0, 0, logicalWidth, logicalHeight)
    gradient.addColorStop(0, '#151124')
    gradient.addColorStop(.48, '#0d1627')
    gradient.addColorStop(1, '#111827')
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, logicalWidth, logicalHeight)

    const glow = ctx.createRadialGradient(1180, 120, 0, 1180, 120, 640)
    glow.addColorStop(0, 'rgba(124,58,237,.26)')
    glow.addColorStop(1, 'rgba(124,58,237,0)')
    ctx.fillStyle = glow
    ctx.fillRect(0, 0, logicalWidth, 700)

    drawText(ctx, 'PT 生涯', margin, 104, { size: 52, weight: 800 })
    drawText(ctx, 'MoviePilot · PT数据统计', margin, 151, { size: 23, color: '#a9a2ba' })
    drawText(ctx, `更新于 ${props.overview.generated_at?.replace('T', ' ') || ''}`, logicalWidth - margin, 108, {
      size: 21, color: '#a9a2ba', align: 'right',
    })
    drawText(ctx, `${selectedSites.value.length} 个站点`, logicalWidth - margin, 148, {
      size: 24, weight: 700, color: '#86efac', align: 'right',
    })

    let y = 210
    chosenSummary.forEach((field, index) => {
      const column = index % 4
      const row = Math.floor(index / 4)
      const gap = 18
      const width = (logicalWidth - margin * 2 - gap * 3) / 4
      const x = margin + column * (width + gap)
      const top = y + row * 142
      roundedRect(ctx, x, top, width, 122, 22, 'rgba(255,255,255,.065)', 'rgba(255,255,255,.11)')
      drawText(ctx, field.label, x + 24, top + 40, { size: 19, color: '#aaa3bb' })
      drawText(ctx, summaryValue(field.key, props.overview.summary || {}), x + 24, top + 88, {
        size: 31, weight: 750, color: siteColors[index % siteColors.length], maxWidth: width - 48,
      })
    })
    y += summaryHeight

    const showSiteNames = visibleFields.value.includes('site_name')
    const iconSources = await Promise.all(
      selectedSites.value.map(site => showSiteNames ? getSiteIcon(props.api, site.site_id) : ''),
    )
    const icons = await Promise.all(iconSources.map(loadImage))
    selectedSites.value.forEach((site, siteIndex) => {
      roundedRect(ctx, margin, y, logicalWidth - margin * 2, siteCardHeight, 24, 'rgba(255,255,255,.055)', 'rgba(255,255,255,.1)')
      ctx.beginPath()
      ctx.arc(margin + 47, y + 48, 25, 0, Math.PI * 2)
      ctx.fillStyle = `${siteColors[siteIndex % siteColors.length]}33`
      ctx.fill()
      if (icons[siteIndex]) {
        ctx.save()
        ctx.beginPath()
        ctx.arc(margin + 47, y + 48, 22, 0, Math.PI * 2)
        ctx.clip()
        ctx.drawImage(icons[siteIndex], margin + 25, y + 26, 44, 44)
        ctx.restore()
      } else {
        const avatarLabel = showSiteNames
          ? String(site.site_name || '?').slice(0, 1)
          : String(siteIndex + 1)
        drawText(ctx, avatarLabel, margin + 47, y + 57, {
          size: 25, weight: 800, align: 'center', color: siteColors[siteIndex % siteColors.length],
        })
      }
      drawText(ctx, showSiteNames ? site.site_name : `站点 ${siteIndex + 1}`, margin + 88, y + 45, {
        size: 28, weight: 760, maxWidth: 450,
      })
      if (visibleFields.value.includes('updated_day')) {
        drawText(ctx, `数据日期 ${site.updated_day || '暂无'}`, logicalWidth - margin - 24, y + 52, {
          size: 19, color: '#9690a5', align: 'right',
        })
      }

      chosenSite.forEach((field, index) => {
        const column = index % 4
        const row = Math.floor(index / 4)
        const width = (logicalWidth - margin * 2 - 48) / 4
        const x = margin + 24 + column * (width + 8)
        const top = y + 116 + row * 86
        drawText(ctx, field.label, x, top, { size: 17, color: '#8f899d' })
        drawText(ctx, siteValue(field.key, site), x, top + 34, {
          size: 22, weight: 650, color: field.key === 'download' ? '#fb7185' : field.key === 'upload' ? '#6ee7b7' : '#eee9f6', maxWidth: width - 20,
        })
      })
      y += siteCardHeight + 22
    })

    await new Promise(resolve => {
      canvas.toBlob(blob => {
        if (!blob) return resolve()
        const url = URL.createObjectURL(blob)
        const anchor = document.createElement('a')
        anchor.href = url
        anchor.download = `PT生涯-${props.overview.server_date || 'latest'}.png`
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
  <VDialog v-model="opened" max-width="920" scrollable>
    <VCard rounded="xl">
      <VCardTitle class="d-flex align-center ga-2 pa-5">
        <VIcon icon="mdi-image-outline" color="primary" />
        导出 PT 生涯
      </VCardTitle>
      <VDivider />
      <VCardText class="pa-5">
        <VSelect
          v-model="selectedSiteIds"
          :items="overview.sites || []"
          item-title="site_name"
          item-value="site_id"
          label="图片包含的站点"
          multiple
          chips
          closable-chips
          variant="outlined"
          class="mb-5"
        />

        <div class="text-subtitle-2 mb-2">汇总区显示字段</div>
        <div class="field-grid mb-5">
          <VCheckbox
            v-for="field in summaryFields"
            :key="field.key"
            v-model="visibleFields"
            :value="field.key"
            :label="field.label"
            density="compact"
            hide-details
          />
        </div>

        <div class="text-subtitle-2 mb-2">站点卡片显示字段</div>
        <div class="field-grid">
          <VCheckbox
            v-for="field in siteFields"
            :key="field.key"
            v-model="visibleFields"
            :value="field.key"
            :label="field.label"
            density="compact"
            hide-details
          />
        </div>
        <VAlert type="info" variant="tonal" class="mt-5">
          隐藏字段后图片会自动重新排版；站点越多，导出的高清 PNG 会自动增长高度。
        </VAlert>
      </VCardText>
      <VDivider />
      <VCardActions class="pa-4 justify-end">
        <VBtn variant="text" @click="opened = false">取消</VBtn>
        <VBtn
          color="primary"
          variant="flat"
          prepend-icon="mdi-download"
          :loading="generating"
          :disabled="!selectedSites.length"
          @click="generateImage"
        >生成高清 PNG</VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>

<style scoped>
.field-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 4px 12px;
}

@media (max-width: 700px) {
  .field-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
