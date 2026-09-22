import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, a as actionOrder, b as actionMetaFallback, n as normalizeNotificationModel } from './_plugin-vue_export-helper-DIfCoLzf.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,createBlock:_createBlock,unref:_unref,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass,withKeys:_withKeys} = await importShared('vue');


const _hoisted_1 = {
  key: 0,
  class: "detail-loading"
};
const _hoisted_2 = {
  key: 2,
  class: "detail-grid"
};
const _hoisted_3 = { class: "detail-card__top" };

const {computed,onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'MediaServerNotifyPlus' },
},
  emits: ['action', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const loading = ref(true);
const loadError = ref('');
const model = ref({ types: [] });
const enabledTypes = computed(() => new Set(model.value.types || []));
const targetStorageKey = computed(() => `mediaservernotifyplus:edit:${props.pluginId}`);

function unwrap(value) {
  let current = value;
  for (let index = 0; index < 2; index += 1) {
    if (!current || typeof current !== 'object') break
    if (Object.prototype.hasOwnProperty.call(current, 'data')) current = current.data;
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
  loading.value = true;
  loadError.value = '';
  try {
    const response = unwrap(await props.api.get(`plugin/form/${props.pluginId}`, { feedback: 'silent' }));
    model.value = normalizeNotificationModel(response?.model || response || { types: [] });
  } catch (error) {
    loadError.value = error?.message || '读取插件配置失败';
  } finally {
    loading.value = false;
  }
}
onMounted(load);

function openConfig(action = '') {
  if (action) {
    try { window.sessionStorage.setItem(targetStorageKey.value, action); } catch (_) { /* ignore */ }
  }
  emit('switch');
}

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createBlock(_component_VCard, {
    class: "detail-shell",
    rounded: "xl",
    variant: "flat"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VCardTitle, { class: "detail-header" }, {
        default: _withCtx(() => [
          _createVNode(_component_VAvatar, {
            color: "primary",
            variant: "tonal"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VIcon, { icon: "mdi-bell-ring-outline" })
            ]),
            _: 1
          }),
          _cache[3] || (_cache[3] = _createElementVNode("div", null, [
            _createElementVNode("div", null, "媒体库通知"),
            _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "点击通知类型可进入设置")
          ], -1)),
          _createVNode(_component_VBtn, {
            class: "ml-auto",
            "prepend-icon": "mdi-tune-variant",
            variant: "tonal",
            onClick: _cache[0] || (_cache[0] = $event => (openConfig()))
          }, {
            default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
              _createTextVNode("设置", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_VBtn, {
            icon: "mdi-close",
            variant: "text",
            onClick: _cache[1] || (_cache[1] = $event => (_ctx.$emit('close')))
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VDivider),
      _createVNode(_component_VCardText, { class: "pa-5" }, {
        default: _withCtx(() => [
          (loading.value)
            ? (_openBlock(), _createElementBlock("div", _hoisted_1, [
                _createVNode(_component_VProgressCircular, {
                  indeterminate: "",
                  color: "primary"
                }),
                _cache[4] || (_cache[4] = _createElementVNode("span", null, "正在读取通知设置", -1))
              ]))
            : (loadError.value)
              ? (_openBlock(), _createBlock(_component_VAlert, {
                  key: 1,
                  type: "error",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(loadError.value), 1)
                  ]),
                  _: 1
                }))
              : (_openBlock(), _createElementBlock("div", _hoisted_2, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(actionOrder), (action) => {
                    return (_openBlock(), _createBlock(_component_VCard, {
                      key: action,
                      class: "detail-card",
                      variant: "outlined",
                      tabindex: "0",
                      onClick: $event => (openConfig(action)),
                      onKeydown: _withKeys($event => (openConfig(action)), ["enter"])
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCardText, null, {
                          default: _withCtx(() => [
                            _createElementVNode("div", _hoisted_3, [
                              _createVNode(_component_VIcon, {
                                icon: _unref(actionMetaFallback)[action].icon,
                                color: "primary"
                              }, null, 8, ["icon"]),
                              _createElementVNode("span", {
                                class: _normalizeClass(["detail-state", { 'detail-state--off': !enabledTypes.value.has(action) }])
                              }, null, 2)
                            ]),
                            _createElementVNode("strong", null, _toDisplayString(actionLabel(action)), 1),
                            _createElementVNode("small", null, _toDisplayString(enabledTypes.value.has(action) ? `已启用 · ${fieldCount(action)} 个字段` : '已停用'), 1)
                          ]),
                          _: 2
                        }, 1024)
                      ]),
                      _: 2
                    }, 1032, ["onClick", "onKeydown"]))
                  }), 128))
                ]))
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-5480d056"]]);

export { Page as default };
