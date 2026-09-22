import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,withModifiers:_withModifiers,toDisplayString:_toDisplayString,normalizeClass:_normalizeClass,withKeys:_withKeys} = await importShared('vue');


const _hoisted_1 = { class: "notify-config" };
const _hoisted_2 = { class: "page-header" };
const _hoisted_3 = {
  class: "card-grid",
  "aria-label": "通知类型"
};
const _hoisted_4 = { class: "event-card__top" };
const _hoisted_5 = { class: "event-icon" };
const _hoisted_6 = { class: "event-card__copy" };
const _hoisted_7 = { class: "event-card__status" };
const _hoisted_8 = { class: "page-actions" };
const _hoisted_9 = { class: "save-hint" };
const _hoisted_10 = { class: "d-flex ga-2" };
const _hoisted_11 = { class: "dialog-title-icon" };
const _hoisted_12 = { class: "message-preview" };
const _hoisted_13 = { class: "message-preview__title" };
const _hoisted_14 = {
  key: 0,
  class: "message-preview__media"
};
const _hoisted_15 = { class: "field-list-heading" };
const _hoisted_16 = { class: "field-list" };
const _hoisted_17 = ["onDrop"];
const _hoisted_18 = ["aria-label", "onDragstart"];
const _hoisted_19 = { class: "field-identity" };
const _hoisted_20 = { class: "field-key" };
const _hoisted_21 = { class: "field-order-buttons" };
const _hoisted_22 = { class: "dialog-title-icon" };
const _hoisted_23 = { class: "setting-row setting-row--featured" };
const _hoisted_24 = { class: "setting-block" };
const _hoisted_25 = { class: "setting-row" };
const _hoisted_26 = { class: "settings-grid" };
const _hoisted_27 = { class: "setting-row" };
const _hoisted_28 = { class: "setting-block test-block" };
const _hoisted_29 = { class: "settings-grid settings-grid--test" };

const {computed,onMounted,ref,watch} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'MediaServerNotifyPlus' },
  sourcePluginId: { type: String, default: '' },
  nativeSubscribe: { type: Function, default: null },
},
  emits: ['layout', 'save', 'close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const actionOrder = [
  'library_added', 'library_deleted', 'playback_started', 'playback_stopped',
  'playback_paused', 'playback_resumed', 'auth_success', 'auth_failed', 'rated', 'test',
];
const actionIcons = {
  library_added: 'mdi-folder-arrow-down', library_deleted: 'mdi-delete-outline',
  playback_started: 'mdi-play-circle-outline', playback_stopped: 'mdi-stop-circle-outline',
  playback_paused: 'mdi-pause-circle-outline', playback_resumed: 'mdi-play-circle',
  auth_success: 'mdi-login-variant', auth_failed: 'mdi-shield-alert-outline',
  rated: 'mdi-star-circle-outline', test: 'mdi-flask-outline',
};
const fallbackMeta = {
  library_added: ['已入库', '媒体文件加入媒体库时通知'],
  library_deleted: ['已删除', '媒体文件从媒体库移除时通知'],
  playback_started: ['开始播放', '用户开始播放媒体时通知'],
  playback_stopped: ['停止播放', '用户停止播放媒体时通知'],
  playback_paused: ['暂停播放', '用户暂停播放媒体时通知'],
  playback_resumed: ['继续播放', '用户继续播放媒体时通知'],
  auth_success: ['登录成功', '用户成功登录媒体服务器时通知'],
  auth_failed: ['登录失败', '媒体服务器登录失败时通知'],
  rated: ['已标记', '用户标记已看、未看或评分时通知'],
  test: ['测试', '用于检查当前通知样式'],
};

const clone = value => JSON.parse(JSON.stringify(value || {}));
const draft = ref(clone(props.initialConfig));
const settingsOpen = ref(false);
const editorOpen = ref(false);
const activeAction = ref('library_added');
const draggingIndex = ref(-1);
const saved = ref(false);

watch(() => props.initialConfig, value => { draft.value = clone(value); }, { deep: true });
onMounted(() => emit('layout', { maxWidth: '76rem' }));

const actionMeta = action => {
  const supplied = draft.value._action_meta?.[action];
  return supplied || { label: fallbackMeta[action][0], description: fallbackMeta[action][1] }
};
const fieldMeta = key => draft.value._field_catalog?.[key] || { label: key };
const activeFields = computed(() => draft.value.field_configs?.[activeAction.value] || []);
const activeMeta = computed(() => actionMeta(activeAction.value));
const enabledTypes = computed(() => new Set(draft.value.types || []));
const serverOptions = computed(() => draft.value._server_options || []);

function isEnabled(action) {
  return enabledTypes.value.has(action)
}
function setEnabled(action, enabled) {
  const next = new Set(draft.value.types || []);
  enabled ? next.add(action) : next.delete(action);
  draft.value.types = actionOrder.filter(item => next.has(item));
}
function openEditor(action) {
  activeAction.value = action;
  editorOpen.value = true;
}
function moveField(from, to) {
  const rows = activeFields.value;
  if (from < 0 || to < 0 || from >= rows.length || to >= rows.length || from === to) return
  const [row] = rows.splice(from, 1);
  rows.splice(to, 0, row);
}
function startDrag(index, event) {
  draggingIndex.value = index;
  event.dataTransfer.effectAllowed = 'move';
}
function dropField(index) {
  moveField(draggingIndex.value, index);
  draggingIndex.value = -1;
}
function resetFields() {
  const original = draft.value._default_field_configs?.[activeAction.value];
  if (original) draft.value.field_configs[activeAction.value] = clone(original);
}
function cleanPayload() {
  const payload = clone(draft.value);
  Object.keys(payload).filter(key => key.startsWith('_')).forEach(key => delete payload[key]);
  delete payload.libraries;
  delete payload.fetch_metadata;
  delete payload.lookup_ip;
  payload.types = actionOrder.filter(action => (payload.types || []).includes(action));
  return payload
}
function saveConfig() {
  emit('save', cleanPayload());
  saved.value = true;
  window.setTimeout(() => { saved.value = false; }, 1800);
}
function enabledFieldCount(action) {
  return (draft.value.field_configs?.[action] || []).filter(row => row.enabled).length
}

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VCheckbox = _resolveComponent("VCheckbox");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VSelect = _resolveComponent("VSelect");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createElementVNode("header", _hoisted_2, [
      _cache[21] || (_cache[21] = _createElementVNode("div", null, [
        _createElementVNode("div", { class: "eyebrow" }, "MEDIA LIBRARY NOTIFICATIONS"),
        _createElementVNode("h1", null, "通知模板"),
        _createElementVNode("p", null, "选择通知类型，设置需要展示的内容和顺序。")
      ], -1)),
      _createVNode(_component_VBtn, {
        class: "settings-button",
        variant: "tonal",
        "prepend-icon": "mdi-tune-variant",
        onClick: _cache[0] || (_cache[0] = $event => (settingsOpen.value = true))
      }, {
        default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
          _createTextVNode(" 设置 ", -1)
        ]))]),
        _: 1
      })
    ]),
    (!draft.value.enabled)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          class: "mb-5",
          type: "warning",
          variant: "tonal",
          icon: "mdi-bell-off-outline"
        }, {
          default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
            _createTextVNode(" 插件当前未启用。你仍可编辑模板，启用后才会发送通知。 ", -1)
          ]))]),
          _: 1
        }))
      : _createCommentVNode("", true),
    _createElementVNode("section", _hoisted_3, [
      (_openBlock(), _createElementBlock(_Fragment, null, _renderList(actionOrder, (action) => {
        return _createVNode(_component_VCard, {
          key: action,
          class: _normalizeClass(["event-card", { 'event-card--disabled': !isEnabled(action) }]),
          variant: "outlined",
          tabindex: "0",
          onClick: $event => (openEditor(action)),
          onKeydown: _withKeys($event => (openEditor(action)), ["enter"])
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardText, { class: "event-card__body" }, {
              default: _withCtx(() => [
                _createElementVNode("div", _hoisted_4, [
                  _createElementVNode("div", _hoisted_5, [
                    _createVNode(_component_VIcon, {
                      icon: actionIcons[action],
                      size: "26"
                    }, null, 8, ["icon"])
                  ]),
                  _createVNode(_component_VSwitch, {
                    "model-value": isEnabled(action),
                    color: "primary",
                    "hide-details": "",
                    density: "compact",
                    "aria-label": `启用${actionMeta(action).label}`,
                    onClick: _cache[1] || (_cache[1] = _withModifiers(() => {}, ["stop"])),
                    "onUpdate:modelValue": $event => (setEnabled(action, $event))
                  }, null, 8, ["model-value", "aria-label", "onUpdate:modelValue"])
                ]),
                _createElementVNode("div", _hoisted_6, [
                  _createElementVNode("h2", null, _toDisplayString(actionMeta(action).label), 1),
                  _createElementVNode("p", null, _toDisplayString(actionMeta(action).description), 1)
                ])
              ]),
              _: 2
            }, 1024),
            _createElementVNode("div", _hoisted_7, [
              _createElementVNode("span", {
                class: _normalizeClass(["status-dot", { 'status-dot--off': !isEnabled(action) }])
              }, null, 2),
              _createElementVNode("span", null, _toDisplayString(isEnabled(action) ? `已启用 · ${enabledFieldCount(action)} 个字段` : '已停用'), 1),
              _createVNode(_component_VIcon, {
                class: "ml-auto",
                icon: "mdi-chevron-right",
                size: "20"
              })
            ])
          ]),
          _: 2
        }, 1032, ["class", "onClick", "onKeydown"])
      }), 64))
    ]),
    _createElementVNode("footer", _hoisted_8, [
      _createElementVNode("span", _hoisted_9, [
        _createVNode(_component_VIcon, {
          icon: "mdi-information-outline",
          size: "18"
        }),
        _cache[23] || (_cache[23] = _createTextVNode(" 字段没有数据时会自动隐藏整行", -1))
      ]),
      _createElementVNode("div", _hoisted_10, [
        _createVNode(_component_VBtn, {
          variant: "text",
          onClick: _cache[2] || (_cache[2] = $event => (_ctx.$emit('close')))
        }, {
          default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
            _createTextVNode("取消", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VBtn, {
          color: "primary",
          variant: "flat",
          "prepend-icon": "mdi-content-save-outline",
          onClick: saveConfig
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(saved.value ? '已保存' : '保存设置'), 1)
          ]),
          _: 1
        })
      ])
    ]),
    _createVNode(_component_VDialog, {
      modelValue: editorOpen.value,
      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((editorOpen).value = $event)),
      "max-width": "760",
      scrollable: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { class: "editor-dialog" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "dialog-header" }, {
              default: _withCtx(() => [
                _createElementVNode("div", _hoisted_11, [
                  _createVNode(_component_VIcon, {
                    icon: actionIcons[activeAction.value]
                  }, null, 8, ["icon"])
                ]),
                _createElementVNode("div", null, [
                  _cache[25] || (_cache[25] = _createElementVNode("div", { class: "dialog-kicker" }, "通知内容", -1)),
                  _createElementVNode("div", null, _toDisplayString(activeMeta.value.label), 1)
                ]),
                _createVNode(_component_VBtn, {
                  class: "ml-auto",
                  icon: "mdi-close",
                  variant: "text",
                  onClick: _cache[3] || (_cache[3] = $event => (editorOpen.value = false))
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, { class: "dialog-body" }, {
              default: _withCtx(() => [
                _createElementVNode("div", _hoisted_12, [
                  _createElementVNode("div", _hoisted_13, _toDisplayString(activeMeta.value.label), 1),
                  (!['auth_success', 'auth_failed', 'test'].includes(activeAction.value))
                    ? (_openBlock(), _createElementBlock("div", _hoisted_14, "示例影片 (2026)"))
                    : _createCommentVNode("", true),
                  _cache[26] || (_cache[26] = _createElementVNode("div", { class: "message-preview__note" }, "下方勾选的字段将按当前顺序继续展示", -1))
                ]),
                _createElementVNode("div", _hoisted_15, [
                  _cache[28] || (_cache[28] = _createElementVNode("div", null, [
                    _createElementVNode("strong", null, "可通知内容"),
                    _createElementVNode("span", null, "拖动左侧手柄排序，只能修改展示名称")
                  ], -1)),
                  _createVNode(_component_VBtn, {
                    size: "small",
                    variant: "text",
                    "prepend-icon": "mdi-restore",
                    onClick: resetFields
                  }, {
                    default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
                      _createTextVNode("恢复默认", -1)
                    ]))]),
                    _: 1
                  })
                ]),
                _createElementVNode("div", _hoisted_16, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(activeFields.value, (row, index) => {
                    return (_openBlock(), _createElementBlock("div", {
                      key: row.key,
                      class: _normalizeClass(["field-row", { 'field-row--disabled': !row.enabled }]),
                      onDragover: _cache[5] || (_cache[5] = _withModifiers(() => {}, ["prevent"])),
                      onDrop: _withModifiers($event => (dropField(index)), ["prevent"])
                    }, [
                      _createElementVNode("button", {
                        class: "drag-handle",
                        type: "button",
                        draggable: "true",
                        "aria-label": `拖动${row.label}排序`,
                        onDragstart: $event => (startDrag(index, $event)),
                        onDragend: _cache[4] || (_cache[4] = $event => (draggingIndex.value = -1))
                      }, [
                        _createVNode(_component_VIcon, { icon: "mdi-drag-vertical" })
                      ], 40, _hoisted_18),
                      _createElementVNode("div", _hoisted_19, [
                        _createElementVNode("div", _hoisted_20, _toDisplayString(fieldMeta(row.key).label), 1),
                        _createVNode(_component_VTextField, {
                          modelValue: row.label,
                          "onUpdate:modelValue": $event => ((row.label) = $event),
                          label: "展示名称",
                          density: "compact",
                          variant: "outlined",
                          maxlength: "30",
                          "hide-details": ""
                        }, null, 8, ["modelValue", "onUpdate:modelValue"])
                      ]),
                      _createElementVNode("div", _hoisted_21, [
                        _createVNode(_component_VBtn, {
                          disabled: index === 0,
                          icon: "mdi-chevron-up",
                          size: "x-small",
                          variant: "text",
                          onClick: $event => (moveField(index, index - 1))
                        }, null, 8, ["disabled", "onClick"]),
                        _createVNode(_component_VBtn, {
                          disabled: index === activeFields.value.length - 1,
                          icon: "mdi-chevron-down",
                          size: "x-small",
                          variant: "text",
                          onClick: $event => (moveField(index, index + 1))
                        }, null, 8, ["disabled", "onClick"])
                      ]),
                      _createVNode(_component_VCheckbox, {
                        modelValue: row.enabled,
                        "onUpdate:modelValue": $event => ((row.enabled) = $event),
                        color: "primary",
                        "hide-details": "",
                        "aria-label": `展示${row.label}`
                      }, null, 8, ["modelValue", "onUpdate:modelValue", "aria-label"])
                    ], 42, _hoisted_17))
                  }), 128))
                ])
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, { class: "dialog-actions" }, {
              default: _withCtx(() => [
                _createElementVNode("span", null, _toDisplayString(enabledFieldCount(activeAction.value)) + " / " + _toDisplayString(activeFields.value.length) + " 个字段已启用", 1),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "flat",
                  onClick: _cache[6] || (_cache[6] = $event => (editorOpen.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
                    _createTextVNode("完成", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: settingsOpen.value,
      "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((settingsOpen).value = $event)),
      "max-width": "720",
      scrollable: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { class: "settings-dialog" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "dialog-header" }, {
              default: _withCtx(() => [
                _createElementVNode("div", _hoisted_22, [
                  _createVNode(_component_VIcon, { icon: "mdi-tune-variant" })
                ]),
                _cache[30] || (_cache[30] = _createElementVNode("div", null, [
                  _createElementVNode("div", { class: "dialog-kicker" }, "GLOBAL SETTINGS"),
                  _createElementVNode("div", null, "通知设置")
                ], -1)),
                _createVNode(_component_VBtn, {
                  class: "ml-auto",
                  icon: "mdi-close",
                  variant: "text",
                  onClick: _cache[8] || (_cache[8] = $event => (settingsOpen.value = false))
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, { class: "dialog-body settings-stack" }, {
              default: _withCtx(() => [
                _createElementVNode("div", _hoisted_23, [
                  _cache[31] || (_cache[31] = _createElementVNode("div", null, [
                    _createElementVNode("strong", null, "启用插件"),
                    _createElementVNode("span", null, "接收媒体服务器事件并发送通知")
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: draft.value.enabled,
                    "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((draft.value.enabled) = $event)),
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"])
                ]),
                _createElementVNode("div", _hoisted_24, [
                  _cache[32] || (_cache[32] = _createElementVNode("label", null, "媒体服务器", -1)),
                  _createVNode(_component_VSelect, {
                    modelValue: draft.value.mediaservers,
                    "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((draft.value.mediaservers) = $event)),
                    items: serverOptions.value,
                    "item-title": "title",
                    "item-value": "value",
                    placeholder: "未选择时监听全部媒体服务器",
                    multiple: "",
                    chips: "",
                    "closable-chips": "",
                    clearable: "",
                    variant: "outlined",
                    "hide-details": ""
                  }, null, 8, ["modelValue", "items"]),
                  _cache[33] || (_cache[33] = _createElementVNode("small", null, "选择需要接收通知的 Emby、Jellyfin 或 Plex 实例。", -1))
                ]),
                _createElementVNode("div", _hoisted_25, [
                  _cache[34] || (_cache[34] = _createElementVNode("div", null, [
                    _createElementVNode("strong", null, "聚合剧集入库"),
                    _createElementVNode("span", null, "同一剧集在窗口内只发送一条通知")
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: draft.value.aggregate_enabled,
                    "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((draft.value.aggregate_enabled) = $event)),
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"])
                ]),
                (draft.value.aggregate_enabled)
                  ? (_openBlock(), _createBlock(_component_VTextField, {
                      key: 0,
                      modelValue: draft.value.aggregate_time,
                      "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((draft.value.aggregate_time) = $event)),
                      modelModifiers: { number: true },
                      label: "聚合窗口（秒）",
                      type: "number",
                      min: "1",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]))
                  : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_26, [
                  _createVNode(_component_VTextField, {
                    modelValue: draft.value.dedupe_library,
                    "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((draft.value.dedupe_library) = $event)),
                    modelModifiers: { number: true },
                    label: "入库/删除去重（秒）",
                    type: "number",
                    min: "0",
                    variant: "outlined",
                    "hide-details": ""
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VTextField, {
                    modelValue: draft.value.dedupe_playback,
                    "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((draft.value.dedupe_playback) = $event)),
                    modelModifiers: { number: true },
                    label: "播放事件去重（秒）",
                    type: "number",
                    min: "0",
                    variant: "outlined",
                    "hide-details": ""
                  }, null, 8, ["modelValue"])
                ]),
                _createElementVNode("div", _hoisted_27, [
                  _cache[35] || (_cache[35] = _createElementVNode("div", null, [
                    _createElementVNode("strong", null, "停止时发送待聚合消息"),
                    _createElementVNode("span", null, "插件重载或停止时不丢弃队列")
                  ], -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: draft.value.flush_on_stop,
                    "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((draft.value.flush_on_stop) = $event)),
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"])
                ]),
                _createElementVNode("div", _hoisted_28, [
                  _cache[36] || (_cache[36] = _createElementVNode("label", null, "测试通知", -1)),
                  _createElementVNode("div", _hoisted_29, [
                    _createVNode(_component_VSelect, {
                      modelValue: draft.value.preview_type,
                      "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((draft.value.preview_type) = $event)),
                      items: actionOrder.map(value => ({ value, title: actionMeta(value).label })),
                      label: "通知类型",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue", "items"]),
                    _createVNode(_component_VSwitch, {
                      modelValue: draft.value.send_test,
                      "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((draft.value.send_test) = $event)),
                      label: "保存时发送",
                      color: "primary",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ])
                ]),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  icon: "mdi-message-badge-outline"
                }, {
                  default: _withCtx(() => [...(_cache[37] || (_cache[37] = [
                    _createTextVNode(" 消息渠道遵循 MoviePilot 全局设置，通知类型固定为“媒体库”。 ", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, { class: "dialog-actions" }, {
              default: _withCtx(() => [
                _cache[39] || (_cache[39] = _createElementVNode("span", null, "设置随主页面一起保存", -1)),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "flat",
                  onClick: _cache[18] || (_cache[18] = $event => (settingsOpen.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                    _createTextVNode("完成", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"])
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-1ed0edc4"]]);

export { Config as default };
