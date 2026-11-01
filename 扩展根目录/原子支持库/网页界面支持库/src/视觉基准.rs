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
.hs-table{width:100%;border-collapse:collapse;font-size:14px}
.hs-table th{text-align:left;padding:10px 12px;background:#fafafa;color:var(--hs-text-sub);font-weight:600;border-bottom:1px solid var(--hs-border);white-space:nowrap}
.hs-table td{padding:10px 12px;border-bottom:1px solid var(--hs-border);color:var(--hs-text-sub)}
.hs-table tbody tr:hover td{background:var(--hs-primary-light)}
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
.hs-button-primary{background:var(--hs-primary);border-color:var(--hs-primary);color:#fff}
.hs-button-primary:hover{background:var(--hs-primary-hover);border-color:var(--hs-primary-hover);color:#fff}
.hs-button-success{background:var(--hs-success);border-color:var(--hs-success);color:#fff}
.hs-button-warning{background:var(--hs-warning);border-color:var(--hs-warning);color:#fff}
.hs-button-danger{background:var(--hs-danger);border-color:var(--hs-danger);color:#fff}
.hs-button-success:hover,.hs-button-warning:hover,.hs-button-danger:hover{opacity:.88;color:#fff}
.hs-layout{display:flex;min-height:100vh;background:var(--hs-bg)}
.hs-sidebar{width:240px;flex:0 0 240px;background:#fff;border-right:1px solid var(--hs-border);display:flex;flex-direction:column}
.hs-sidebar-title{padding:20px;font-size:18px;font-weight:700;color:var(--hs-primary);letter-spacing:2px;border-bottom:1px solid var(--hs-border)}
.hs-menu{padding:8px 0}
.hs-menu-item{display:flex;align-items:center;gap:10px;height:48px;padding:0 20px;font-size:14px;color:var(--hs-text-sub);border-right:3px solid transparent;text-decoration:none}
.hs-menu-item:hover{background:#f5f7fa;color:var(--hs-primary)}
.hs-menu-item.is-active{background:var(--hs-primary-light);color:var(--hs-primary);border-right-color:var(--hs-primary);font-weight:600}
.hs-main{flex:1 1 auto;display:flex;flex-direction:column;min-width:0}
.hs-topbar{height:60px;display:flex;align-items:center;padding:0 24px;background:#fff;border-bottom:1px solid var(--hs-border);font-size:16px;font-weight:600;color:var(--hs-text)}
.hs-content{padding:24px;flex:1 1 auto;overflow:auto}
.hs-chat{display:flex;flex-direction:column;gap:12px;padding:2px}
.hs-chat-empty{padding:36px 0;text-align:center;color:var(--hs-text-weak);font-size:13px}
.hs-chat-msg{display:flex;gap:10px;align-items:flex-start;max-width:84%}
.hs-chat-msg.is-user{margin-left:auto;flex-direction:row-reverse}
.hs-chat-avatar{flex:0 0 32px;display:flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:9px;background:var(--hs-primary-light);color:var(--hs-primary);font-size:13px;font-weight:600}
.hs-chat-msg.is-user .hs-chat-avatar{background:var(--hs-primary);color:#fff}
.hs-chat-body{min-width:0}
.hs-chat-meta{margin-bottom:4px;font-size:12px;color:var(--hs-text-weak)}
.hs-chat-msg.is-user .hs-chat-meta{text-align:right}
.hs-chat-text{padding:10px 12px;border-radius:10px;background:#f5f7fa;font-size:14px;line-height:1.62;color:var(--hs-text);white-space:pre-wrap;word-break:break-word}
.hs-chat-msg.is-user .hs-chat-text{background:var(--hs-primary);color:#fff}
.hs-tree{display:flex;flex-direction:column;min-width:0;font-size:14px;color:var(--hs-text)}
.hs-tree-node{min-width:0}
.hs-tree-sidebar{display:flex;align-items:stretch;border-radius:10px;overflow:hidden;background:#fff;box-shadow:var(--hs-shadow-1);min-height:0}
.hs-tree-sidebar-pane{display:flex;flex-direction:column;background:#f7f8fa;border-right:1px solid rgba(60,60,67,.12);padding:10px 8px;min-width:0;overflow:auto}
.hs-tree-sidebar-title{padding:0 6px 8px;font-size:12px;font-weight:600;color:var(--hs-text-weak);letter-spacing:.4px}
.hs-tree-menu{display:flex;flex-direction:column;gap:2px}
.hs-tree-menu-item{display:flex;align-items:center;gap:8px;padding:7px 9px;border-radius:8px;font-size:13px;color:var(--hs-text);cursor:default;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
a.hs-tree-menu-item{text-decoration:none}
.hs-tree-menu-item.is-active{background:var(--hs-primary-light);color:var(--hs-primary);font-weight:600}
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
.hs-tree-icon-label{line-height:1.25;max-width:88px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:var(--hs-clamp,2);-webkit-box-orient:vertical;word-break:break-word}
.hs-tree-overlay{position:fixed;inset:0;z-index:60;display:flex;align-items:center;justify-content:center}
.hs-tree-overlay.is-hidden{display:none !important}
.hs-tree-toggle{cursor:pointer}
.hs-tree-window{position:relative;display:flex;flex-direction:column;overflow:hidden;box-sizing:border-box;width:100%;height:100%}
.hs-tree-window.is-hidden{display:none !important}
.hs-tree-window-bar{display:flex;align-items:center;gap:8px;flex:none;padding:0 10px;user-select:none;cursor:default}
.hs-tree-window-title{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:inherit}
.hs-tree-window-close,.hs-tree-window-min,.hs-tree-window-max{flex:none;border:0;background:transparent;cursor:pointer;font:inherit;line-height:1;padding:4px 7px;border-radius:6px;color:inherit;opacity:.72}
.hs-tree-window-close:hover,.hs-tree-window-min:hover,.hs-tree-window-max:hover{background:rgba(0,0,0,.08);opacity:1}
.hs-tree-window-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.hs-tree-window.is-min{height:auto !important}
.hs-tree-window.is-min .hs-tree-window-body{display:none}
.hs-tree-canvas-item.is-min{height:auto !important}
.hs-tree-canvas-item.is-max{left:0 !important;top:0 !important;width:100% !important;height:100% !important;z-index:30 !important}
.hs-tree-window-body{flex:1;min-height:0;overflow:auto;display:flex;flex-direction:column}
.hs-tree-window-body>.hs-tree-node{min-height:0}
.hs-tree-link{text-decoration:none;color:inherit}
.hs-tree-link:hover{opacity:.72}
</style>"#
        .to_string()
}

/// 常量：V3 外壳观感（历史能力专用，4928 不用）。
pub(crate) fn 历史外壳样式文本() -> String {
    r#"<style>
:root{--desktop-menu-bar-height:30px;--desktop-dock-height:66px;--desktop-dock-bottom-gap:12px;--desktop-work-bottom-inset:78px;--desktop-system-blue:#0a84ff;--desktop-ink:rgba(20,20,22,.88);--desktop-wallpaper-ink:rgba(255,255,255,.96);--desktop-material-menubar:rgba(255,255,255,.08);--desktop-material-dock:rgba(255,255,255,.22);--desktop-material-window:rgba(246,246,248,.97);--desktop-shadow-window:0 28px 80px rgba(0,0,0,.36),0 8px 24px rgba(0,0,0,.18),0 0 0 .5px rgba(0,0,0,.2);--desktop-shadow-window-inactive:0 10px 28px rgba(0,0,0,.18),0 2px 8px rgba(0,0,0,.08),0 0 0 .5px rgba(0,0,0,.12);--desktop-shadow-dock:0 18px 40px rgba(0,0,0,.32),0 2px 8px rgba(0,0,0,.16),inset 0 .5px 0 rgba(255,255,255,.5);--desktop-shadow-popover:0 16px 40px rgba(0,0,0,.24),0 0 0 .5px rgba(0,0,0,.08),inset 0 .5px 0 rgba(255,255,255,.55);--desktop-radius-control:6px;--desktop-radius-status-control:4px;--desktop-radius-menu:12px;--desktop-radius-popover:14px;--desktop-radius-panel:16px;--window-radius:13px;--window-maximized-radius:10px;--window-titlebar-height:39px;--window-bg:rgba(246,246,248,.97);--window-border:rgba(0,0,0,.12);--window-titlebar-bg:rgba(236,236,238,.96);--window-titlebar-border:rgba(0,0,0,.08);--window-shadow:var(--desktop-shadow-window);--window-shadow-active:var(--desktop-shadow-window);--desktop-radius-window:13px;--desktop-radius-chip:999px;--desktop-dock-radius:18px;--desktop-radius-launchpad:22px;--desktop-dock-filter:blur(24px) saturate(150%);--desktop-menu-filter:blur(28px) saturate(150%);--desktop-launchpad-panel-max-width:920px;--desktop-launchpad-panel-max-height:640px;--desktop-launchpad-filter:blur(34px) saturate(175%);--desktop-font-menu:600 13px/1.45 -apple-system,BlinkMacSystemFont,'SF Pro Text','PingFang SC',sans-serif;--desktop-font-body:400 13px/1.45 -apple-system,BlinkMacSystemFont,'SF Pro Text','PingFang SC',sans-serif;--desktop-font-caption:400 11px/1.35 -apple-system,BlinkMacSystemFont,'SF Pro Text','PingFang SC',sans-serif;--desktop-duration-fast:130ms;--desktop-duration-standard:210ms;--desktop-ease-standard:cubic-bezier(.32,.72,0,1);--desktop-bg-gradient-start:#0b1b2c;--desktop-bg-gradient-middle:#134e5e;--desktop-bg-gradient-end:#2b1d5e;--desktop-icon-text:#f1f5f9;--desktop-icon-selected-bg:rgba(14,165,233,.18);--desktop-icon-selected-border:rgba(125,211,252,.46);}
/* ===== 登录页（照 V3 登录页样式） ===== */
.hs-login-page{display:flex;align-items:center;justify-content:center;min-height:100vh;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%)}
.hs-login-card{width:420px;max-width:90vw;padding:48px 40px;background:#fff;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.15);text-align:center}
.hs-login-icon{margin-bottom:8px;font-size:56px;line-height:1;color:var(--primary-color)}
.hs-login-title{margin:0;font-size:26px;font-weight:700;color:#0f172a}
.hs-login-sub{margin:4px 0 0;font-size:14px;color:#94a3b8}
.hs-login-form{margin-top:32px;text-align:left}
.hs-login-field{position:relative;margin-bottom:22px}
.hs-login-prefix{position:absolute;left:12px;top:50%;transform:translateY(-50%);font-size:16px;line-height:1;color:#a8abb2}
.hs-login-input{width:100%;height:40px;padding:0 12px 0 36px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;font-size:14px;font-family:inherit;line-height:38px;color:#303133}
.hs-login-input::placeholder{color:var(--hs-text-placeholder)}
.hs-login-input:focus{outline:none;border-color:var(--primary-color);box-shadow:0 0 0 2px rgba(64,158,255,.2)}
.hs-login-btn{width:100%;height:40px;border:1px solid var(--primary-color);border-radius:4px;background:var(--primary-color);color:#fff;font-size:15px;font-family:inherit;line-height:38px;letter-spacing:2px;cursor:pointer}
.hs-login-btn:hover{background:var(--hs-primary-hover);border-color:var(--hs-primary-hover)}
.hs-login-error{margin-top:16px;padding:8px 12px;border-radius:4px;background:#fef0f0;color:#f56c6c;font-size:13px;text-align:left}
/* ===== 桌面外壳（macOS 观感） ===== */
body.hs-desk-body{margin:0;overflow:hidden}
.hs-desk{position:relative;width:100%;height:100vh;overflow:hidden;background:linear-gradient(160deg,var(--desktop-bg-gradient-start) 0%,var(--desktop-bg-gradient-middle) 52%,var(--desktop-bg-gradient-end) 100%);color:var(--desktop-wallpaper-ink)}
.hs-wallpaper{position:absolute;inset:0;z-index:0;background-size:cover;background-position:center}
.hs-wallpaper::after{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(3,7,18,.02),rgba(3,7,18,.28))}
.hs-menubar{position:absolute;top:0;left:0;right:0;z-index:var(--z-menu-bar);display:flex;align-items:center;justify-content:space-between;height:var(--desktop-menu-bar-height);padding:0 12px 0 10px;background:var(--desktop-material-menubar);border-bottom:.5px solid rgba(255,255,255,.14);backdrop-filter:var(--desktop-menu-filter);-webkit-backdrop-filter:var(--desktop-menu-filter);color:var(--desktop-wallpaper-ink);font:400 13px/1 -apple-system,BlinkMacSystemFont,'SF Pro Text','PingFang SC','Helvetica Neue',sans-serif;letter-spacing:-.01em}
.hs-menubar-left,.hs-menubar-right{display:flex;align-items:center;gap:2px;height:100%}
.hs-menubar-brand{padding:0 9px;font-weight:700;letter-spacing:.5px}
.hs-menubar-app{padding:0 9px;font-weight:700;opacity:.96}
.hs-menubar-item{display:flex;align-items:center;height:22px;padding:0 9px;border-radius:var(--desktop-radius-status-control);font-weight:400;cursor:default}
.hs-menubar-item:hover{background:rgba(255,255,255,.16)}
.hs-menubar-clock{padding:0 6px 0 8px;font-variant-numeric:tabular-nums}
.hs-menubar-badge{display:inline-block;min-width:16px;height:16px;margin-left:4px;padding:0 4px;border-radius:var(--desktop-radius-chip);background:#ff3b30;color:#fff;font:600 10px/16px var(--desktop-font-body);text-align:center}
.hs-icon-layer{position:absolute;left:0;right:0;top:var(--desktop-menu-bar-height);bottom:var(--desktop-work-bottom-inset);z-index:1;pointer-events:none}
.hs-icon-group{position:absolute;width:100px;padding:8px 4px;pointer-events:auto}
.hs-icon-group-title{padding:0 6px 6px;font:600 11px/1.3 var(--desktop-font-caption);letter-spacing:.6px;color:rgba(255,255,255,.62)}
.hs-icon-grid{position:absolute;inset:0}
.hs-icon{position:absolute;display:flex;flex-direction:column;align-items:center;gap:3px;width:88px;padding:8px 4px;border-radius:12px;cursor:default;user-select:none;pointer-events:auto;transition:left .15s cubic-bezier(.25,.46,.45,.94),top .15s cubic-bezier(.25,.46,.45,.94),background .15s,box-shadow .15s,transform .15s}
.hs-icon:hover{background:rgba(255,255,255,.12);box-shadow:inset 0 0 0 1px rgba(255,255,255,.12),0 8px 18px rgba(15,23,42,.12);transform:translateY(-1px)}
.hs-icon.is-selected{background:var(--desktop-icon-selected-bg);box-shadow:inset 0 0 0 1px var(--desktop-icon-selected-border)}
.hs-icon-glyph{display:flex;align-items:center;justify-content:center;width:48px;height:48px;border-radius:12px;background:rgba(255,255,255,.22);font-size:26px;line-height:1;backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}
.hs-icon-label{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;max-width:80px;overflow:hidden;font:11px/1.35 -apple-system,BlinkMacSystemFont,'SF Pro Text','PingFang SC',sans-serif;color:#f1f5f9;text-align:center;text-shadow:0 1px 3px rgba(0,0,0,.5);word-break:break-all}
/* ===== 窗口 ===== */
.hs-win{position:absolute;display:flex;flex-direction:column;min-width:320px;min-height:180px;border-radius:var(--window-radius);background:var(--window-bg);color:var(--desktop-ink);border:.5px solid var(--window-border);box-shadow:var(--window-shadow);overflow:hidden}
.hs-win.is-active{border-color:rgba(255,255,255,.62);box-shadow:var(--desktop-shadow-window-active)}
.hs-win.is-minimized{display:none}
.hs-win-bar{display:flex;align-items:center;gap:8px;height:var(--window-titlebar-height);padding:0 14px;background:linear-gradient(180deg,rgba(255,255,255,.28),rgba(255,255,255,.04)),var(--window-titlebar-bg);border-bottom:.5px solid var(--window-titlebar-border);box-shadow:inset 0 .5px 0 rgba(255,255,255,.65);backdrop-filter:blur(18px) saturate(155%);-webkit-backdrop-filter:blur(18px) saturate(155%)}
.hs-win-dots{display:flex;align-items:center;gap:8px}
.hs-win-dot{width:12px;height:12px;padding:0;border:none;border-radius:50%;font-size:0;cursor:pointer}
.hs-win-dot.is-close{background:#ff5f57}
.hs-win-dot.is-min{background:#febc2e}
.hs-win-dot.is-max{background:#28c840}
.hs-win-title{flex:1 1 auto;margin-right:52px;overflow:hidden;font:600 13px/1.45 var(--desktop-font-body);color:var(--desktop-ink);text-align:center;text-overflow:ellipsis;white-space:nowrap}
.hs-win-body{flex:1 1 auto;overflow:auto;padding:16px;background:#fff}
/* ===== Dock ===== */
.hs-dock{position:absolute;left:50%;bottom:var(--desktop-dock-bottom-gap);z-index:var(--z-dock);display:flex;align-items:center;gap:6px;min-height:var(--desktop-dock-height);padding:7px 9px;border:.5px solid rgba(255,255,255,.28);border-radius:var(--desktop-dock-radius);background:var(--desktop-material-dock);box-shadow:var(--desktop-shadow-dock);backdrop-filter:var(--desktop-dock-filter);-webkit-backdrop-filter:var(--desktop-dock-filter);transform:translateX(-50%)}
.hs-dock-item{position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;width:48px;height:48px;border-radius:12px;background:rgba(255,255,255,.35);font-size:26px;line-height:1;cursor:default;transition:transform var(--desktop-duration-fast) var(--desktop-ease-standard)}
.hs-dock-item:hover{transform:translateY(-4px) scale(1.12)}
.hs-dock-dot{position:absolute;bottom:-6px;width:4px;height:4px;border-radius:50%;background:rgba(20,20,22,.55)}
.hs-dock-sep{width:1px;height:38px;margin:0 4px;background:rgba(0,0,0,.14)}
/* ===== 启动器 ===== */
.hs-launchpad[hidden]{display:none}
.hs-launchpad{position:fixed;inset:0;z-index:var(--z-launchpad);display:flex;align-items:center;justify-content:center;padding:28px 20px;background:rgba(20,22,26,.42);backdrop-filter:blur(10px) saturate(120%);-webkit-backdrop-filter:blur(10px) saturate(120%)}
.hs-launchpad-panel{width:min(var(--desktop-launchpad-panel-max-width),92vw);max-height:min(var(--desktop-launchpad-panel-max-height),84vh);overflow:auto;padding:16px 18px 20px;border-radius:var(--desktop-radius-launchpad);background:rgba(246,246,248,.86);box-shadow:var(--desktop-shadow-popover);backdrop-filter:var(--desktop-launchpad-filter);-webkit-backdrop-filter:var(--desktop-launchpad-filter);color:var(--desktop-ink)}
.hs-launchpad-title{margin:0 0 10px;font:600 20px/1.3 var(--desktop-font-body);letter-spacing:.5px}
.hs-launchpad-search{width:100%;height:32px;padding:0 11px;margin-bottom:16px;border:1px solid rgba(0,0,0,.12);border-radius:10px;background:rgba(255,255,255,.72);font:var(--desktop-font-body);color:var(--desktop-ink)}
.hs-launchpad-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:18px 10px}
.hs-launchpad-group{margin:0 0 16px}
.hs-launchpad-group-title{margin:0 0 8px;padding-left:2px;font:600 12px/1.3 -apple-system,BlinkMacSystemFont,'SF Pro Text','PingFang SC',sans-serif;color:rgba(60,60,67,.62);letter-spacing:.4px}
.hs-launchpad-item{display:flex;flex-direction:column;align-items:center;gap:8px;padding:8px 4px 4px;border-radius:14px;cursor:default}
.hs-launchpad-item:hover{background:rgba(0,0,0,.06)}
.hs-launchpad-glyph{display:flex;align-items:center;justify-content:center;width:58px;height:58px;border-radius:14px;background:rgba(255,255,255,.72);box-shadow:var(--hs-shadow-1);font-size:30px;line-height:1}
.hs-launchpad-label{max-width:104px;overflow:hidden;font:var(--desktop-font-caption);color:var(--desktop-ink);text-align:center;text-overflow:ellipsis;white-space:nowrap}
</style>"#
        .to_string()
}

/// 常量：中性 + 历史外壳（历史能力拼整页时用）。
pub(crate) fn 完整样式文本() -> String {
    format!("{}{}", 中性样式文本(), 历史外壳样式文本())
}
