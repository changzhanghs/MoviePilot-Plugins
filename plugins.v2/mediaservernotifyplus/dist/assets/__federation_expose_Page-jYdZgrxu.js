import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,withCtx:_withCtx,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');



const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'MediaServerNotifyPlus' },
},
  emits: ['action', 'switch', 'close'],
  setup(__props) {




return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createBlock(_component_VCard, {
    rounded: "xl",
    variant: "outlined"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VCardTitle, { class: "d-flex align-center ga-3 pa-5" }, {
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
          _cache[1] || (_cache[1] = _createElementVNode("div", null, [
            _createElementVNode("div", null, "媒体库通知"),
            _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "通知样式请在插件配置中管理")
          ], -1)),
          _createVNode(_component_VBtn, {
            class: "ml-auto",
            icon: "mdi-close",
            variant: "text",
            onClick: _cache[0] || (_cache[0] = $event => (_ctx.$emit('close')))
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VDivider),
      _createVNode(_component_VCardText, { class: "pa-5" }, {
        default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
          _createTextVNode("每种媒体事件都能独立选择字段、调整顺序和修改展示名称。", -1)
        ]))]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};

export { _sfc_main as default };
