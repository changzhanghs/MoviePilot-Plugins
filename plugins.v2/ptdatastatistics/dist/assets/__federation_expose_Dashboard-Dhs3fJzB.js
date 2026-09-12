import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, s as siteColors, f as formatBytes, a as _sfc_main$1, u as unwrapResponse } from './SiteAvatar-DwA7AJDm.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,unref:_unref,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,normalizeStyle:_normalizeStyle,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,createTextVNode:_createTextVNode} = await importShared('vue');


const _hoisted_1 = { class: "pt-dashboard" };
const _hoisted_2 = { class: "pt-dashboard__header" };
const _hoisted_3 = { class: "pt-dashboard__totals" };
const _hoisted_4 = { class: "total-pill" };
const _hoisted_5 = { class: "total-pill total-pill--upload" };
const _hoisted_6 = { class: "total-pill total-pill--download" };
const _hoisted_7 = {
  key: 0,
  class: "pt-dashboard__body"
};
const _hoisted_8 = { class: "donut-wrap" };
const _hoisted_9 = { class: "donut__hole" };
const _hoisted_10 = { class: "site-scroll" };
const _hoisted_11 = { class: "site-row__avatar" };
const _hoisted_12 = { class: "site-row__name" };
const _hoisted_13 = { class: "site-row__metric site-row__metric--upload" };
const _hoisted_14 = { class: "site-row__metric site-row__metric--download" };
const _hoisted_15 = { class: "site-row__share" };
const _hoisted_16 = {
  key: 1,
  class: "pt-dashboard__empty"
};

const {computed,onMounted,onUnmounted,ref,watch} = await importShared('vue');


const _sfc_main = {
  __name: 'Dashboard',
  props: {
  api: { type: Object, default: () => ({}) },
  config: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'PTDataStatistics' },
  sourcePluginId: { type: String, default: '' },
  nativeSubscribe: { type: Function, default: null },
  allowRefresh: { type: Boolean, default: true },
},
  setup(__props) {

const props = __props;

const loading = ref(false);
const overview = ref({
  server_date: '',
  summary: {},
  today_sites: [],
});
let refreshTimer;

const pluginBase = computed(() => `plugin/${props.pluginId || 'PTDataStatistics'}`);
const sites = computed(() => overview.value.today_sites || []);

const donutBackground = computed(() => {
  if (!sites.value.length) return 'conic-gradient(rgba(var(--v-theme-on-surface), .1) 0 100%)'
  let offset = 0;
  const stops = sites.value.map((site, index) => {
    const start = offset;
    offset += Number(site.contribution || 0);
    return `${siteColors[index % siteColors.length]} ${start}% ${Math.min(offset, 100)}%`
  });
  if (offset < 100) stops.push(`rgba(var(--v-theme-on-surface), .1) ${offset}% 100%`);
  return `conic-gradient(${stops.join(', ')})`
});

async function loadOverview() {
  if (!props.allowRefresh && overview.value.server_date) return
  loading.value = true;
  try {
    const data = await props.api.get(`${pluginBase.value}/overview`, { feedback: 'silent' });
    overview.value = unwrapResponse(data) || overview.value;
  } finally {
    loading.value = false;
  }
}

watch(() => props.allowRefresh, enabled => enabled && loadOverview());

onMounted(() => {
  loadOverview();
  refreshTimer = window.setInterval(loadOverview, 60000);
});

onUnmounted(() => {
  if (refreshTimer) window.clearInterval(refreshTimer);
});

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createElementVNode("div", _hoisted_2, [
      _createElementVNode("div", _hoisted_3, [
        _createElementVNode("div", _hoisted_4, [
          _createVNode(_component_VIcon, {
            class: "total-pill__icon",
            icon: "mdi-calendar-blank-outline",
            size: "20"
          }),
          _cache[0] || (_cache[0] = _createElementVNode("span", null, "统计日期", -1)),
          _createElementVNode("strong", null, _toDisplayString(overview.value.server_date || '暂无'), 1)
        ]),
        _createElementVNode("div", _hoisted_5, [
          _createVNode(_component_VIcon, {
            class: "total-pill__icon",
            icon: "mdi-arrow-up",
            size: "20",
            color: "success"
          }),
          _cache[1] || (_cache[1] = _createElementVNode("span", null, "上传增量", -1)),
          _createElementVNode("strong", null, _toDisplayString(_unref(formatBytes)(overview.value.summary.today_upload)), 1)
        ]),
        _createElementVNode("div", _hoisted_6, [
          _createVNode(_component_VIcon, {
            class: "total-pill__icon",
            icon: "mdi-arrow-down",
            size: "20",
            color: "error"
          }),
          _cache[2] || (_cache[2] = _createElementVNode("span", null, "下载增量", -1)),
          _createElementVNode("strong", null, _toDisplayString(_unref(formatBytes)(overview.value.summary.today_download)), 1)
        ])
      ]),
      (loading.value)
        ? (_openBlock(), _createBlock(_component_VProgressLinear, {
            key: 0,
            indeterminate: "",
            color: "primary",
            height: "2"
          }))
        : _createCommentVNode("", true)
    ]),
    (sites.value.length)
      ? (_openBlock(), _createElementBlock("div", _hoisted_7, [
          _createElementVNode("div", _hoisted_8, [
            _createElementVNode("div", {
              class: "donut",
              style: _normalizeStyle({ background: donutBackground.value })
            }, [
              _createElementVNode("div", _hoisted_9, [
                _createElementVNode("strong", null, _toDisplayString(sites.value.length), 1),
                _cache[3] || (_cache[3] = _createElementVNode("span", null, "个站点", -1))
              ])
            ], 4)
          ]),
          _createElementVNode("div", _hoisted_10, [
            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(sites.value, (site, index) => {
              return (_openBlock(), _createElementBlock("div", {
                key: site.site_id || site.site_name,
                class: "site-row"
              }, [
                _createElementVNode("div", _hoisted_11, [
                  _createVNode(_sfc_main$1, {
                    api: __props.api,
                    site: site,
                    size: 36
                  }, null, 8, ["api", "site"])
                ]),
                _createElementVNode("div", _hoisted_12, [
                  _createElementVNode("strong", null, _toDisplayString(site.site_name), 1)
                ]),
                _createElementVNode("div", _hoisted_13, "↑ " + _toDisplayString(_unref(formatBytes)(site.daily_upload)), 1),
                _createElementVNode("div", _hoisted_14, "↓ " + _toDisplayString(_unref(formatBytes)(site.daily_download)), 1),
                _createElementVNode("div", _hoisted_15, [
                  _createElementVNode("i", {
                    style: _normalizeStyle({ backgroundColor: _unref(siteColors)[index % _unref(siteColors).length] })
                  }, null, 4),
                  _createTextVNode(" " + _toDisplayString(site.contribution.toFixed(1)) + "% ", 1)
                ])
              ]))
            }), 128))
          ])
        ]))
      : (_openBlock(), _createElementBlock("div", _hoisted_16, [
          _createVNode(_component_VIcon, {
            icon: "mdi-chart-donut-variant",
            size: "48",
            color: "secondary"
          }),
          _cache[4] || (_cache[4] = _createElementVNode("strong", null, "今日暂无站点流量", -1)),
          _cache[5] || (_cache[5] = _createElementVNode("span", null, "仅显示今日上传或下载大于零、且基线有效的站点", -1))
        ]))
  ]))
}
}

};
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-4101b6b4"]]);

export { Dashboard as default };
