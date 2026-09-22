<script setup>
import { ref } from 'vue'
import Config from './components/Config.vue'

const fields = {
  library_added: ['season_episode', 'library', 'category', 'file_count', 'media_type', 'year', 'rating', 'region', 'status', 'genres', 'actors', 'overview', 'server', 'channel', 'time', 'media_source', 'media_id', 'album', 'artist'],
  library_deleted: ['season_episode', 'library', 'media_type', 'year', 'server', 'channel', 'time', 'media_source', 'media_id', 'album', 'artist'],
  playback_started: ['season_episode', 'user', 'device', 'ip', 'ip_location', 'progress', 'overview', 'library', 'media_type', 'year', 'server', 'channel', 'time', 'play_link'],
  playback_stopped: ['season_episode', 'user', 'device', 'ip', 'ip_location', 'progress', 'overview', 'library', 'media_type', 'year', 'server', 'channel', 'time', 'play_link'],
  playback_paused: ['season_episode', 'user', 'device', 'ip', 'ip_location', 'progress', 'overview', 'library', 'server', 'channel', 'time', 'play_link'],
  playback_resumed: ['season_episode', 'user', 'device', 'ip', 'ip_location', 'progress', 'overview', 'library', 'server', 'channel', 'time', 'play_link'],
  auth_success: ['user', 'device', 'ip', 'ip_location', 'server', 'channel', 'time'],
  auth_failed: ['user', 'device', 'ip', 'ip_location', 'server', 'channel', 'time'],
  rated: ['season_episode', 'user', 'library', 'media_type', 'year', 'rating', 'server', 'channel', 'time', 'media_source', 'media_id'],
  test: ['server', 'channel', 'time'],
}
const labels = { season_episode: '季集', library: '媒体库', category: '分类', file_count: '文件数量', media_type: '媒体类型', year: '年份', rating: '评分', region: '地区', status: '状态', genres: '类型', actors: '演员', overview: '剧情简介', server: '服务器', channel: '媒体服务', time: '时间', media_source: '媒体来源', media_id: '媒体 ID', album: '专辑', artist: '歌手', user: '用户', device: '设备 / 客户端', ip: 'IP', ip_location: 'IP 归属地', progress: '播放进度', play_link: '播放链接' }
const actions = { library_added: ['已入库', '媒体文件加入媒体库时通知'], library_deleted: ['已删除', '媒体文件从媒体库移除时通知'], playback_started: ['开始播放', '用户开始播放媒体时通知'], playback_stopped: ['停止播放', '用户停止播放媒体时通知'], playback_paused: ['暂停播放', '用户暂停播放媒体时通知'], playback_resumed: ['继续播放', '用户继续播放媒体时通知'], auth_success: ['登录成功', '用户成功登录媒体服务器时通知'], auth_failed: ['登录失败', '媒体服务器登录失败时通知'], rated: ['已标记', '用户标记已看、未看或评分时通知'], test: ['测试', '用于检查当前通知样式'] }
const defaultEnabled = new Set(['season_episode', 'category', 'file_count', 'rating', 'server', 'time', 'overview', 'user', 'device', 'ip', 'progress'])
const config = ref({
  enabled: true,
  types: Object.keys(actions),
  mediaservers: ['家庭影音'],
  field_configs: Object.fromEntries(Object.entries(fields).map(([action, keys]) => [action, keys.map(key => ({ key, label: labels[key], enabled: defaultEnabled.has(key) }))])),
  aggregate_enabled: true, aggregate_time: 15, dedupe_library: 30, dedupe_playback: 30,
  flush_on_stop: false, preview_type: 'library_added', send_test: false,
  _action_meta: Object.fromEntries(Object.entries(actions).map(([key, value]) => [key, { label: value[0], description: value[1] }])),
  _field_catalog: Object.fromEntries(Object.entries(labels).map(([key, label]) => [key, { label }])),
  _server_options: [
    { title: '家庭影音', value: '家庭影音' },
    { title: '客厅 Plex', value: '客厅 Plex' },
  ],
})
config.value._default_field_configs = JSON.parse(JSON.stringify(config.value.field_configs))
</script>

<template>
  <VApp><VMain><VContainer class="py-8" style="max-width: 1180px"><Config :initial-config="config" @save="config = $event" /></VContainer></VMain></VApp>
</template>
