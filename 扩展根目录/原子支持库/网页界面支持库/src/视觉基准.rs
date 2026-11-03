//! 界面样式真源，分两套，互不越界。
//!
//! - [`中性样式文本`]：结构必需的最小观感（重置、业务区、表格/表单/输入/按钮、聊天流、组件树骨架）。
//!   字号、颜色、圆角、阴影、模糊这些观感值一律由调用方在组件树声明里给；这里只保证"不给也还像界面"。
//! - [`历史外壳样式文本`]：登录页 / 桌面外壳 / 窗口 / Dock / 启动器 的 V3 观感，只服务 4910–4927 这批历史能力。
//!   4928 组件树不输出这一段 —— 产品外观归调用方声明，底座保持中性。

/// 常量：中性样式（4928 组件树只发这一段）。
pub(crate) fn 中性样式文本() -> String {
    r#"<style>
:root{--primary-color:#409eff;--hs-primary:#409eff;--hs-primary-hover:#337ecc;--hs-primary-light:#ecf5ff;--hs-success:#67c23a;--hs-warning:#e6a23c;--hs-danger:#f56c6c;--hs-info:#909399;--hs-bg:#f0f2f5;--hs-card:#ffffff;--hs-border:#e4e7ed;--hs-text:#303133;--hs-text-sub:#606266;--hs-text-weak:#909399;--hs-text-placeholder:#c0c4cc;--hs-radius-base:4px;--hs-radius-card:8px;--hs-radius-panel:12px;--hs-shadow-1:0 1px 3px rgba(0,0,0,.06);--hs-shadow-2:0 4px 12px rgba(0,0,0,.08);--hs-shadow-3:0 8px 24px rgba(0,0,0,.12);--z-menu-bar:12000;--z-dock:11000;--z-launchpad:14000;}
*{box-sizing:border-box}
html,body{margin:0;padding:0;height:100%}
body{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','PingFang SC','Microsoft YaHei',sans-serif;background:var(--hs-bg);color:var(--hs-text);-webkit-font-smoothing:antialiased;font-size:14px}
.hs-page{padding:24px;max-width:1280px;margin:0 auto}
.hs-title{margin:0 0 16px;font-size:22px;font-weight:700;letter-spacing:.5px;color:var(--hs-text)}
.hs-card{background:var(--hs-card);border:1px solid var(--hs-border);border-radius:var(--hs-radius-card);padding:20px;margin-bottom:16px;box-shadow:var(--hs-shadow-1)}
.hs-table-scroll{overflow:auto;max-width:100%;min-width:0}
.表头内容容器{display:flex;align-items:center;gap:6px;min-width:0;justify-content:inherit}
.表头标题文本{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis}
.表头排序控件{display:inline-flex;flex-direction:column;flex:0 0 18px;align-items:stretch}
.表头排序按钮{display:block;width:18px;height:13px;min-width:0;padding:0;border:0;border-radius:2px;background:transparent;color:#909399;font-size:9px;line-height:13px;text-align:center;cursor:pointer}
.表头排序按钮:hover,.表头排序按钮[aria-pressed="true"]{background:var(--hs-primary-light);color:var(--hs-primary)}
.表头排序按钮:focus-visible{outline:2px solid var(--hs-primary);outline-offset:1px}
.hs-table[data-固定列宽] td{overflow:hidden;text-overflow:ellipsis}
.hs-table[data-固定行高="true"] tbody td{height:var(--表格行高);padding-top:0;padding-bottom:0;white-space:nowrap!important;line-height:calc(var(--表格行高) - 1px)}
.hs-table[data-固定行高="true"] tbody .hs-input{height:calc(var(--表格行高) - 1px);line-height:normal;padding-top:0;padding-bottom:0}
.hs-table{width:100%;border-collapse:collapse;font-size:var(--hs-table-font,14px)}
.hs-table th{text-align:left;padding:var(--hs-cell-pad,10px 12px);background:var(--hs-th-bg,#fafafa);color:var(--hs-th-ink,var(--hs-text-sub));font-weight:600;border-bottom:1px solid var(--hs-td-line,var(--hs-border));white-space:nowrap}
.hs-table td{background:var(--hs-td-bg,transparent);padding:var(--hs-cell-pad,10px 12px);border-bottom:1px solid var(--hs-td-line,var(--hs-border));color:var(--hs-td-ink,var(--hs-text-sub))}
.hs-table tbody td{position:relative}
.hs-table tbody td:has(.hs-input){background:#fff}
.单元格编辑占位{visibility:hidden}
.hs-table tbody .hs-input{position:absolute;left:0;top:0;right:0;bottom:0;width:100%;height:100%;box-sizing:border-box;margin:0;padding:0 12px;font:inherit;line-height:normal;color:inherit;text-align:inherit;background:#fff;border:1px solid var(--hs-primary,#409eff);border-radius:2px;box-shadow:0 0 0 2px rgba(64,158,255,.14);outline:none}
.hs-table.热点跟踪 tbody tr:hover td{background:var(--hs-row-hover,var(--hs-primary-light))}
.hs-card.斑马纹 .hs-table tbody tr:nth-child(even) td{background:var(--hs-row-alt,#fafafa)}
.hs-card.斑马纹 .hs-table.热点跟踪 tbody tr:nth-child(even):hover td{background:var(--hs-row-hover,var(--hs-primary-light))}
.hs-card.表头固定 .hs-table thead th{position:sticky;top:0;z-index:2}
.hs-table:not(.无表格线) th,.hs-table:not(.无表格线) td{border-right:1px solid var(--hs-td-line,var(--hs-border))}
.hs-table.无表格线 th,.hs-table.无表格线 td{border-bottom:0}
.hs-table .热点{cursor:pointer}
.hs-table .非热点{cursor:default}
.hs-table .已选中 td{background:var(--hs-row-hover,var(--hs-primary-light))}
.hs-table .表头图标,.hs-table .表项图标,.hs-table .表项状态图标{vertical-align:middle;object-fit:contain;margin:0 4px}
.hs-table.小图标视图,.hs-table.大图标视图{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:var(--图标间距,8px)}
.hs-table.小图标视图 thead,.hs-table.大图标视图 thead{display:contents}
.hs-table.小图标视图 tbody,.hs-table.大图标视图 tbody{display:contents}
.hs-table.小图标视图 tr,.hs-table.大图标视图 tr{display:block;padding:8px;border:1px solid var(--hs-border)}
.hs-table.大图标视图 .表项图标{width:48px;height:48px;display:block}
.hs-table.平面滚动条{overflow-x:auto}
.hs-table.热点标注 .热点:hover{text-decoration:underline}
.hs-table .非热点:not(:hover){text-decoration:underline}
.hs-table.隐藏失焦选择项:not(:focus-within) tr.已选中{background:transparent!important;outline:none!important}
.hs-table.隐藏失焦选择项:not(:focus-within) tr.已选中 td{background:transparent!important}
.hs-table.列表视图{display:block;columns:180px auto}
.hs-table.列表视图,.hs-table.小图标视图,.hs-table.大图标视图{width:auto!important;table-layout:auto!important}
.hs-table.列表视图 thead{display:none}
.hs-table.列表视图 colgroup,.hs-table.小图标视图 colgroup,.hs-table.大图标视图 colgroup{display:none}
.hs-table.列表视图 tbody{display:contents}
.hs-table.列表视图 tr{display:block;break-inside:avoid}
.hs-table.列表视图 td{display:block}
.hs-table.列表视图 td:not(:first-child){display:none}
.hs-table.小图标视图 thead,.hs-table.大图标视图 thead{display:none}
.hs-table.小图标视图 td,.hs-table.大图标视图 td{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis}
.hs-table.小图标视图 td[data-hs-cell-column]:not([data-hs-cell-column="0"]),.hs-table.大图标视图 td[data-hs-cell-column]:not([data-hs-cell-column="0"]){display:none}
.hs-table.图标居左.小图标视图,.hs-table.图标居左.大图标视图{display:flex;flex-flow:column wrap;height:400px;align-content:start}
.hs-table.图标居左.小图标视图 tr,.hs-table.图标居左.大图标视图 tr{width:140px}
.hs-table.图标居中 tbody tr{text-align:center}
.hs-table.图标居中 .表项图标{margin-left:auto;margin-right:auto}
.hs-table.图标居右 tbody tr{text-align:right}
.hs-table.图标居右 .表项图标{margin-left:auto;margin-right:0}
.hs-table.图标居中 tbody td{text-align:center!important}
.hs-table.图标居右 tbody td{text-align:right!important}
.hs-table.小图标视图:not(.自动排列图标),.hs-table.大图标视图:not(.自动排列图标){grid-template-columns:repeat(auto-fill,120px);justify-content:start}
.hs-card.平面滚动条 .hs-table-scroll{scrollbar-width:thin;scrollbar-color:#a8abb2 transparent}
.hs-card.平面滚动条 .hs-table-scroll::-webkit-scrollbar{width:6px;height:6px}
.hs-card.平面滚动条 .hs-table-scroll::-webkit-scrollbar-thumb{background:#a8abb2;border-radius:0}
.hs-form-item{margin-bottom:16px}
.hs-form-label{display:block;margin-bottom:6px;font-size:13px;color:var(--hs-text-sub);font-weight:500}
.hs-input{width:100%;height:32px;padding:0 11px;border:1px solid #dcdfe6;border-radius:var(--hs-radius-base);font-size:14px;font-family:inherit;color:var(--hs-text);background:#fff;line-height:30px}
.hs-select{width:100%;height:32px;padding:0 8px;border:1px solid #dcdfe6;border-radius:var(--hs-radius-base);font-size:14px;font-family:inherit;color:var(--hs-text);background:#fff}
.hs-input::placeholder{color:var(--hs-text-placeholder)}
.hs-input:focus,.hs-select:focus{outline:none;border-color:var(--hs-primary);box-shadow:0 0 0 2px rgba(64,158,255,.2)}
.hs-dialog{background:var(--hs-card);border-radius:var(--hs-radius-panel);padding:20px;border:1px solid var(--hs-border);box-shadow:var(--hs-shadow-3)}
.hs-dialog-title{font-size:16px;font-weight:600;margin:0 0 12px;color:var(--hs-text)}
.hs-dialog-body{font-size:14px;color:var(--hs-text-sub);margin-bottom:16px;line-height:1.6}
.hs-dialog-actions{display:flex;justify-content:flex-end;gap:8px}
.hs-button{display:inline-block;height:32px;padding:0 15px;border:1px solid #dcdfe6;border-radius:var(--hs-radius-base);background:#fff;font-size:14px;font-family:inherit;line-height:30px;cursor:pointer;color:var(--hs-text-sub)}
.hs-button:hover{background:var(--hs-primary-light);border-color:#c6e2ff;color:var(--hs-primary)}
.hs-button-样式1{background:var(--hs-primary);border-color:var(--hs-primary);color:#fff}
.hs-button-样式1:hover{background:var(--hs-primary-hover);border-color:var(--hs-primary-hover);color:#fff}
.hs-button-样式2{background:var(--hs-success);border-color:var(--hs-success);color:#fff}
.hs-button-样式3{background:var(--hs-warning);border-color:var(--hs-warning);color:#fff}
.hs-button-样式4{background:var(--hs-danger);border-color:var(--hs-danger);color:#fff}
.hs-button-样式2:hover,.hs-button-样式3:hover,.hs-button-样式4:hover{opacity:.88;color:#fff}
.hs-layout{display:flex;min-height:100vh;background:var(--hs-bg)}
.hs-sidebar{width:240px;flex:0 0 240px;background:#fff;border-right:1px solid var(--hs-border);display:flex;flex-direction:column}
.hs-sidebar-title{padding:20px;font-size:18px;font-weight:700;color:var(--hs-primary);letter-spacing:2px;border-bottom:1px solid var(--hs-border)}
.hs-menu{padding:8px 0}
.hs-menu-item{display:flex;align-items:center;gap:10px;height:48px;padding:0 20px;font-size:14px;color:var(--hs-text-sub);border-right:3px solid transparent;text-decoration:none}
.hs-menu-item:hover{background:#f5f7fa;color:var(--hs-primary)}
.hs-menu-item.已激活{background:var(--hs-primary-light);color:var(--hs-primary);border-right-color:var(--hs-primary);font-weight:600}
.hs-main{flex:1 1 auto;display:flex;flex-direction:column;min-width:0}
.hs-topbar{height:60px;display:flex;align-items:center;padding:0 24px;background:#fff;border-bottom:1px solid var(--hs-border);font-size:16px;font-weight:600;color:var(--hs-text)}
.hs-content{padding:24px;flex:1 1 auto;overflow:auto}
.hs-chat{display:flex;flex-direction:column;gap:12px;padding:2px}
.hs-chat-empty{padding:36px 0;text-align:center;color:var(--hs-text-weak);font-size:13px}
.hs-chat-msg{display:flex;gap:10px;align-items:flex-start;max-width:84%}
.hs-chat-msg.本方消息{margin-left:auto;flex-direction:row-reverse}
.hs-chat-avatar{flex:0 0 32px;display:flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:9px;background:var(--hs-primary-light);color:var(--hs-primary);font-size:13px;font-weight:600}
.hs-chat-msg.本方消息 .hs-chat-avatar{background:var(--hs-primary);color:#fff}
.hs-chat-body{min-width:0}
.hs-chat-meta{margin-bottom:4px;font-size:12px;color:var(--hs-text-weak)}
.hs-chat-msg.本方消息 .hs-chat-meta{text-align:right}
.hs-chat-text{padding:10px 12px;border-radius:var(--hs-chat-radius,10px);background:var(--hs-chat-bg,#f5f7fa);font-size:var(--hs-chat-font,14px);line-height:1.62;color:var(--hs-chat-ink,var(--hs-text));white-space:pre-wrap;word-break:break-word}
.hs-chat-msg.本方消息 .hs-chat-text{background:var(--hs-chat-user-bg,var(--hs-primary));color:var(--hs-chat-user-ink,#fff)}
.hs-tree{display:flex;flex-direction:column;min-width:0;font-size:14px;color:var(--hs-text)}
.hs-tree-node{min-width:0}
.hs-tree-sidebar{display:flex;align-items:stretch;border-radius:10px;overflow:hidden;background:#fff;box-shadow:var(--hs-shadow-1);min-height:0}
.hs-tree-sidebar-pane{display:flex;flex-direction:column;background:var(--hs-menu-panel,#f7f8fa);border-right:1px solid rgba(60,60,67,.12);padding:10px 8px;min-width:0;overflow:auto}
.hs-tree-sidebar-title{padding:0 6px 8px;font-size:12px;font-weight:600;color:var(--hs-text-weak);letter-spacing:.4px}
.hs-tree-menu{display:flex;flex-direction:column;gap:2px}
.hs-tree-menu-item{display:flex;align-items:center;gap:8px;padding:var(--hs-menu-pad,7px 9px);border-radius:var(--hs-menu-radius,8px);font-size:var(--hs-menu-font,13px);color:var(--hs-menu-ink,var(--hs-text));cursor:default;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
a.hs-tree-menu-item{text-decoration:none}
.hs-tree-menu-item.已激活{background:var(--hs-menu-active-bg,var(--hs-primary-light));color:var(--hs-menu-active-ink,var(--hs-primary));font-weight:600}
.hs-tree-menu-icon{flex:0 0 auto;font-size:14px;line-height:1}
.hs-tree-menu-label{min-width:0;overflow:hidden;text-overflow:ellipsis}
.hs-tree-sidebar-main{flex:1 1 auto;display:flex;flex-direction:column;gap:12px;padding:14px 16px;min-width:0;overflow:auto}
.hs-tree-panel{background:transparent}
.hs-tree-panel-title{margin:0 0 8px;font-size:13px;font-weight:600;color:var(--hs-text)}
.hs-tree-title{margin:0 0 4px;font-size:17px;font-weight:600;color:var(--hs-text)}
.hs-tree-text{font-size:14px;line-height:1.62;color:var(--hs-text)}
.hs-tree-divider{height:1px;background:rgba(60,60,67,.12);margin:4px 0}
.hs-tree-canvas-item{min-width:0}
.hs-tree-icon{text-align:center;transition:transform .12s ease,background .12s ease}
.hs-tree-icon:hover{background:rgba(255,255,255,.18);transform:translateY(-1px)}
.hs-tree-icon-glyph{line-height:1}
.hs-tree-icon-img{width:1em;height:1em;object-fit:contain}
.hs-tree-icon-mask{display:inline-block;width:1em;height:1em;background-color:currentColor;-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;-webkit-mask-position:center;mask-position:center;-webkit-mask-size:contain;mask-size:contain}
[data-select]{cursor:pointer}
.已选中{background:var(--hs-sel-bg,rgba(14,165,233,.18)) !important;color:var(--hs-sel-ink,inherit) !important;outline:1px solid var(--hs-sel-line,rgba(125,211,252,.46))}
.hs-tree-icon.已选中{border-radius:8px}
.hs-button.已选中,.hs-tree-text.已选中{border-radius:999px}
[data-magnify] .hs-tree-icon{transform-origin:bottom center;will-change:transform}
.hs-tree-icon-label{line-height:1.25;max-width:88px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:var(--hs-clamp,2);-webkit-box-orient:vertical;word-break:break-word}
.hs-tree-overlay{position:fixed;inset:0;z-index:60;display:flex;align-items:center;justify-content:center}
.hs-tree-overlay.已隐藏{display:none !important}
.hs-tree-toggle{cursor:pointer}
.hs-tree-window{position:relative;display:flex;flex-direction:column;overflow:hidden;box-sizing:border-box;width:100%;height:100%}
.hs-tree-window.已隐藏{display:none !important}
.hs-tree-window-bar{position:relative;display:flex;align-items:center;gap:8px;flex:none;padding:0 10px;user-select:none;cursor:default}
.hs-tree-window-title{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:inherit}
[data-窗口壳]:not(.已聚焦) .hs-tree-window{box-shadow:0 6px 20px rgba(0,0,0,.16) !important}
[data-窗口壳]:not(.已聚焦) .hs-tree-window-bar button{background:var(--hs-win-dim,#d6d6d6) !important}
.hs-tree-window-bar button{transition:background-color .12s ease}
.hs-tree-window-bar.标题居中 .hs-tree-window-title{position:absolute;left:0;right:0;text-align:center;pointer-events:none;padding:0 76px}
.hs-tree-window-close,.hs-tree-window-min,.hs-tree-window-max{flex:none;border:0;background:transparent;cursor:pointer;font:inherit;line-height:1;padding:4px 7px;border-radius:6px;color:inherit;opacity:.72}
.hs-tree-window-close:hover,.hs-tree-window-min:hover,.hs-tree-window-max:hover{background:rgba(0,0,0,.08);opacity:1}
.hs-tree-window-close,.hs-tree-window-min,.hs-tree-window-max{display:inline-flex;align-items:center;justify-content:center}
.hs-tree-window-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.hs-tree-window.已最小化{height:auto !important}
.hs-tree-window.已最小化 .hs-tree-window-body{display:none}
.hs-tree-canvas-item.已最小化{height:auto !important}
.hs-tree-canvas-item.已最大化{left:0 !important;top:0 !important;width:100% !important;height:100% !important;z-index:30 !important}
.hs-tree-window-body{flex:1;min-height:0;overflow:auto;display:flex;flex-direction:column}
.hs-tree-window-body>.hs-tree-node{min-height:0}
.hs-tree-link{text-decoration:none;color:inherit}
.hs-tree-link:hover{opacity:.72}
.hs-toast-layer{position:fixed;left:50%;bottom:36px;transform:translateX(-50%);display:flex;flex-direction:column;gap:8px;z-index:9000;pointer-events:none}
.hs-toast{background:rgba(29,29,31,.92);color:#fff;font-size:13px;padding:9px 16px;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.24);transition:opacity .22s,transform .22s}
.hs-toast.已淡出{opacity:0;transform:translateY(8px)}
.hs-confirm-layer{position:fixed;inset:0;background:rgba(15,15,20,.34);display:flex;align-items:center;justify-content:center;z-index:9100}
.hs-confirm{background:#fff;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.28);padding:22px 22px 16px;min-width:280px;max-width:420px}
.hs-confirm-text{font-size:14px;color:var(--hs-text);line-height:1.6;margin-bottom:16px}
.hs-confirm-actions{display:flex;gap:10px;justify-content:flex-end}
.hs-menu{position:fixed;min-width:150px;background:rgba(255,255,255,.98);border:1px solid rgba(60,60,67,.14);border-radius:10px;box-shadow:0 12px 36px rgba(0,0,0,.22);padding:5px;z-index:9200}
.hs-menu-item{padding:7px 12px;border-radius:7px;font-size:13px;color:var(--hs-text);cursor:default;white-space:nowrap}
.hs-menu-item:hover{background:var(--hs-primary);color:#fff}
.hs-pager{display:flex;align-items:center;gap:10px;justify-content:flex-end;padding:8px 4px 0;font-size:12px;color:var(--hs-text-weak)}
.hs-pager-btn{font:inherit;padding:4px 10px;border-radius:7px;border:1px solid rgba(60,60,67,.18);background:#fff;color:var(--hs-text);cursor:pointer}
.hs-pager-btn:disabled{opacity:.45;cursor:default}
.hs-receipt{margin-top:10px;font-size:13px;min-height:18px}
.hs-receipt.成功态{color:#15803D}
.hs-receipt.失败态{color:#B42318}
[data-draggable="1"]{cursor:grab}
[data-draggable="1"].拖动中{opacity:.45}
[data-drop-group].放置目标{outline:1px dashed var(--hs-primary);outline-offset:2px}
th.升序::after{content:" ▲";font-size:10px}
th.降序::after{content:" ▼";font-size:10px}
</style>"#
        .to_string()
}
