import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const source = readFileSync(new URL('../plugins.v2/ptdatastatistics/src/components/PTStatsWorkbench.vue', import.meta.url), 'utf8')
function sourceFunction(start, end) {
  const offset = source.indexOf(start)
  assert(offset >= 0)
  const stop = source.indexOf(end, offset)
  assert(stop > offset)
  return source.slice(offset, stop)
}
function fixture() {
  const requests = []
  const errors = []
  const state = {
    selectedHistoryPeriod: { value: { startDay: '2026-10-04' } },
    selectedHistorySiteId: { value: 1 },
    selectedHistorySite: { value: { site_name: '站点一' } },
    historyScope: { value: 'day' },
    hourlyLoading: { value: false },
    hourlyTraffic: { value: { points: [] } },
    historyLoading: { value: false },
    history: { value: { records: [] } },
    historyFilters: { value: { startDay: '2026-09-05', endDay: '2026-10-04', siteIds: [], includeArchived: true } },
    historyPeriods: { value: [{ key: 'day:2026-10-04' }] },
    selectedHistoryPeriodKey: { value: '' },
    pluginBase: { value: 'plugin/PTDataStatistics' },
    props: { api: { get(path) {
      return new Promise((resolve, reject) => requests.push({ path, resolve, reject }))
    } } },
    withQuery: (path, query) => `${path}?${new URLSearchParams(query)}`,
    unwrapResponse: response => response,
    notify: message => errors.push(message),
  }
  vm.createContext(state)
  vm.runInContext(`let hourlyRequestSequence = 0; let historyRequestSequence = 0;\n${sourceFunction('async function loadHourlyTraffic()', 'function setHistoryChartCanvas')}\n${sourceFunction('async function loadHistory()', 'async function saveSettings()')}`, state)
  return { state, requests, errors }
}

test('older hourly success or failure cannot overwrite the selected site', async () => {
  for (const failure of [false, true]) {
    const { state, requests, errors } = fixture()
    const old = state.loadHourlyTraffic()
    state.selectedHistorySiteId.value = 2
    const latest = state.loadHourlyTraffic()
    requests[1].resolve({ site_id: 2, points: [{ upload: 222 }] })
    await latest
    if (failure) requests[0].reject(new Error('old request failed'))
    else requests[0].resolve({ site_id: 1, points: [{ upload: 111 }] })
    await old
    assert.equal(state.hourlyTraffic.value.site_id, 2)
    assert.equal(state.hourlyTraffic.value.points[0].upload, 222)
    assert.deepEqual(errors, [])
  }
})

test('an old hourly completion cannot clear the latest loading state', async () => {
  const { state, requests } = fixture()
  const old = state.loadHourlyTraffic()
  state.selectedHistoryPeriod.value = { startDay: '2026-10-03' }
  const latest = state.loadHourlyTraffic()
  requests[0].resolve({ day: '2026-10-04', points: [] })
  await old
  assert.equal(state.hourlyLoading.value, true)
  requests[1].resolve({ day: '2026-10-03', points: [] })
  await latest
  assert.equal(state.hourlyTraffic.value.day, '2026-10-03')
  assert.equal(state.hourlyLoading.value, false)
})

test('leaving daily scope invalidates the in-flight hourly request', async () => {
  const { state, requests, errors } = fixture()
  const old = state.loadHourlyTraffic()
  state.historyScope.value = 'week'
  await state.loadHourlyTraffic()
  requests[0].reject(new Error('obsolete daily request'))
  await old
  assert.equal(state.hourlyLoading.value, false)
  assert.deepEqual(errors, [])
})

test('history filters accept only the latest request and preserve its loading state', async () => {
  for (const failure of [false, true]) {
    const { state, requests, errors } = fixture()
    const old = state.loadHistory()
    state.historyFilters.value.siteIds = [2]
    const latest = state.loadHistory()
    if (failure) requests[0].reject(new Error('old request failed'))
    else requests[0].resolve({ records: [{ site_id: 1 }] })
    await old
    assert.equal(state.historyLoading.value, true)
    requests[1].resolve({ records: [{ site_id: 2 }] })
    await latest
    assert.equal(state.history.value.records[0].site_id, 2)
    assert.equal(state.historyLoading.value, false)
    assert.deepEqual(errors, [])
  }
})

test('default 30-day range is independent of browser timezone', () => {
  const previousTimezone = process.env.TZ
  try {
    for (const timezone of ['Asia/Shanghai', 'America/Los_Angeles', 'UTC']) {
      process.env.TZ = timezone
      const state = {
        overview: { value: { last_history_day: '2026-10-04' } },
        historyFilters: { value: { endDay: '', startDay: '' } },
        distributionFilters: { value: { day: '', month: '' } },
      }
      vm.createContext(state)
      vm.runInContext(sourceFunction('function setDefaultRanges()', 'async function loadDistribution()'), state)
      state.setDefaultRanges()
      assert.equal(state.historyFilters.value.startDay, '2026-09-05', timezone)
      assert.equal(state.historyFilters.value.endDay, '2026-10-04', timezone)
    }
  } finally {
    if (previousTimezone === undefined) delete process.env.TZ
    else process.env.TZ = previousTimezone
  }
})

function retirementFixture() {
  const state = {
    overview: { value: { server_date: '2026-10-04' } },
    formatBytes: value => `${value} B`,
    formatNumber: value => String(value),
    normalizedSiteName: value => String(value || '').toLowerCase().replace(/[^\p{L}\p{N}]/gu, ''),
  }
  vm.createContext(state)
  vm.runInContext(sourceFunction('function durationLabel(', 'function levelTrafficRequirements('), state)
  return state
}

test('unknown mandatory requirements remain visible and prevent 100 percent progress', () => {
  const state = retirementFixture()
  const rows = state.requirementRows({ upload: 1000 }, {
    min_upload: 100,
    unsupported_requirements: [
      { key: 'posts', label: '发帖数', target: 10 },
      { key: 'hnrUnsatisfied', label: '未解决 H&R 数', target: 0 },
    ],
  })
  assert.equal(rows.length, 3)
  assert.equal(rows.find(row => row.label === '发帖数').complete, false)
  assert.equal(rows.find(row => row.label === '发帖数').unavailable, true)
  assert.equal(rows.find(row => row.label === '未解决 H&R 数').target, '0')
  assert(state.averageRequirementProgress(rows) < 100)
})

test('selected alternative includes account age and mandatory unknown requirements', () => {
  const state = retirementFixture()
  const rows = state.requirementRows({ upload: 1000, join_at: '2026-09-04' }, {
    min_upload: 100,
    unsupported_requirements: [{ key: 'posts', label: '发帖数', target: 10 }],
    alternatives: [{ min_join_days: 30, min_join_days_strict: true, min_upload: 100 }],
  }, 0)
  assert.equal(rows.length, 4)
  const age = rows.find(row => row.label === '注册时间')
  assert.equal(age.complete, false)
  assert.equal(age.eta, '2026-10-05')
  assert(age.progress < 100)
  assert.equal(rows.find(row => row.label === '发帖数').complete, false)
  assert(state.averageRequirementProgress(rows) < 100)
})

test('alternative account-age condition affects OR completion and missing date stays unknown', () => {
  const state = retirementFixture()
  const level = { alternatives: [{ min_join_days: 30 }, { min_upload: 100 }] }
  const site = { upload: 0, join_at: '2026-09-05' }
  let row = state.requirementRows(site, level)[0]
  assert.equal(row.complete, false)
  assert.match(row.target, /注册/)
  assert(row.progress < 100)
  site.join_at = '2026-09-04'
  row = state.requirementRows(site, level)[0]
  assert.equal(row.complete, true)
  assert.equal(state.averageRequirementProgress([row]), 100)
  delete site.join_at
  row = state.requirementRows(site, level, 0)[0]
  assert.equal(row.complete, false)
  assert.equal(row.unavailable, true)
  assert.equal(row.eta, '—')
})

test('one satisfied alternative is sufficient while unknown alternatives remain pending', () => {
  const state = retirementFixture()
  const level = {
    alternatives: [
      { min_join_days: 30, min_upload: 100 },
      { unsupported_requirements: [{ key: 'posts', label: '发帖数', target: 10 }] },
    ],
  }
  const rows = state.requirementRows({ upload: 100, join_at: '2026-09-04' }, level)
  assert.equal(rows[0].complete, true)
  assert.equal(state.averageRequirementProgress(rows), 100)
  const unknown = state.requirementRows({ upload: 100, join_at: '2026-09-04' }, level, 1)
  assert.equal(unknown[0].complete, false)
  assert.equal(unknown[0].unavailable, true)
})

test('actual reached levels remain completed despite unavailable historical conditions', () => {
  const state = retirementFixture()
  const rows = state.requirementRows({}, {
    reached: true,
    unsupported_requirements: [{ key: 'posts', label: '发帖数', target: 10 }],
    alternatives: [{ min_join_days: 30 }],
  }, 0)
  assert(rows.every(row => row.complete))
  assert.equal(state.averageRequirementProgress(rows), 100)
})

test('strict boundaries and rounding cannot report an incomplete level as 100 percent', () => {
  const state = retirementFixture()
  const rows = state.requirementRows({ upload: 100 }, { min_upload: 100, min_upload_strict: true })
  assert.equal(rows[0].complete, false)
  assert(rows[0].progress < 100)
  assert(state.averageRequirementProgress(rows) < 100)
  assert.equal(state.averageRequirementProgress([
    { complete: true, progress: 100 }, { complete: false, progress: 99.9 },
  ]), 99)
})

test('Spring combines download choices into one shared requirement and shows two points tasks', () => {
  const state = retirementFixture()
  const real = { key: 'real_download', label: '真实下载量', target: '> 2048 GB' }
  const level = {
    name: '精英(Elite)', min_ratio: 1.2, min_ratio_strict: true, min_join_days: 35,
    alternatives: [
      { min_download: 500, min_download_strict: true, min_seeding_points: 100000, min_torrent_uploads: 1, min_torrent_uploads_strict: true },
      { min_download: 500, min_download_strict: true, min_seeding_points: 150000 },
      { unsupported_requirements: [real], min_seeding_points: 100000, min_torrent_uploads: 1, min_torrent_uploads_strict: true },
      { unsupported_requirements: [real], min_seeding_points: 150000 },
    ],
  }
  const site = { site_name: '春天', download: 501, seeding_points: 150000, torrent_uploads: 0, ratio: 1.3, join_at: '2026-08-01' }
  const tasks = state.alternativeTaskOptions(site, level)
  assert.equal(tasks.length, 2)
  assert.equal(tasks[0].subtitle, '积分 ≥ 100000 · 发布 > 1')
  assert.equal(tasks[1].subtitle, '积分 ≥ 150000')
  const first = state.requirementRows(site, level, 0)
  assert.equal(first.filter(row => row.label === '下载量').length, 1)
  assert(first.find(row => row.label === '下载量').target.includes('真实下载量'))
  assert.equal(first.find(row => row.label === '发布数').complete, false)
  assert(state.averageRequirementProgress(first) < 100)
  const second = state.requirementRows(site, level, 1)
  assert.equal(second.some(row => row.label === '发布数'), false)
  assert.equal(state.averageRequirementProgress(second), 100)
  site.download = 500
  const pending = state.requirementRows(site, level, 1)
  assert.equal(pending.find(row => row.label === '下载量').complete, false)
  assert(state.averageRequirementProgress(pending) < 100)
  assert.equal(level.alternatives.length, 4)
  assert.equal(state.alternativeTaskOptions({ site_name: 'Other' }, level).length, 4)
})
