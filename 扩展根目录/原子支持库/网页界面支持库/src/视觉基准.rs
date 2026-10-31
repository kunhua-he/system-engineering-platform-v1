//! V3 视觉基准：界面样式的唯一来源。
//!
//! 取值照抄 V3 前端（Element Plus 业务主题 + macOS 桌面外壳），
//! 这里是唯一的样式真源；能力只返回内联样式，不依赖任何外部 CSS。

/// 业务区主题（Element Plus 观感）与桌面外壳（macOS 观感）的完整样式文本。
pub(crate) fn 基准样式文本() -> String {
    r#"<style>
:root{--hs-primary:#409eff;--hs-primary-hover:#337ecc;--hs-primary-light:#ecf5ff;--hs-success:#67c23a;--hs-warning:#e6a23c;--hs-danger:#f56c6c;--hs-info:#909399;--hs-bg:#f0f2f5;--hs-card:#ffffff;--hs-border:#e4e7ed;--hs-text:#303133;--hs-text-sub:#606266;--hs-text-weak:#909399;--hs-text-placeholder:#c0c4cc;--hs-radius-base:4px;--hs-radius-card:8px;--hs-radius-panel:12px;--hs-shadow-1:0 1px 3px rgba(0,0,0,.06);--hs-shadow-2:0 4px 12px rgba(0,0,0,.08);--hs-shadow-3:0 8px 24px rgba(0,0,0,.12)}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;background:var(--hs-bg);color:var(--hs-text);-webkit-font-smoothing:antialiased;font-size:14px}
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
.hs-button-success:hover{opacity:.88;color:#fff}
.hs-button-warning{background:var(--hs-warning);border-color:var(--hs-warning);color:#fff}
.hs-button-warning:hover{opacity:.88;color:#fff}
.hs-button-danger{background:var(--hs-danger);border-color:var(--hs-danger);color:#fff}
.hs-button-danger:hover{opacity:.88;color:#fff}
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
.hs-desktop{position:relative;min-height:100vh;margin:0;background:linear-gradient(160deg,#1e3f78 0%,#2f6bb5 45%,#7fb0ea 100%);overflow:hidden}
.hs-menubar{height:30px;display:flex;align-items:center;gap:18px;padding:0 14px;background:rgba(255,255,255,.08);backdrop-filter:blur(20px);color:#fff;font-size:13px}
.hs-menubar-brand{font-weight:700;letter-spacing:1px}
.hs-menubar-menu{position:relative;cursor:default;padding:6px 4px}
.hs-menu-drop{display:none;position:absolute;top:26px;left:0;min-width:150px;padding:6px 0;background:rgba(255,255,255,.96);border-radius:12px;box-shadow:var(--hs-shadow-3);color:var(--hs-text-sub);font-size:13px}
.hs-menubar-menu:hover .hs-menu-drop{display:block}
.hs-menu-drop-item{padding:6px 14px;white-space:nowrap}
.hs-menu-drop-item:hover{background:var(--hs-primary-light);color:var(--hs-primary)}
.hs-desktop-icons{display:flex;flex-wrap:wrap;gap:26px;padding:26px 28px;max-width:58%}
.hs-desktop-icon{width:92px;text-align:center;color:#fff;font-size:12px;text-shadow:0 1px 2px rgba(0,0,0,.35)}
.hs-desktop-icon-glyph{display:flex;align-items:center;justify-content:center;width:58px;height:58px;margin:0 auto 6px;background:rgba(255,255,255,.22);border-radius:14px;font-size:28px;line-height:1;backdrop-filter:blur(10px)}
.hs-desktop-icon-label{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hs-window{position:absolute;top:96px;left:50%;transform:translateX(-50%);width:min(920px,74%);max-height:640px;display:flex;flex-direction:column;background:rgba(246,246,248,.97);border-radius:13px;box-shadow:var(--hs-shadow-3);overflow:hidden}
.hs-window-bar{height:38px;display:flex;align-items:center;gap:8px;padding:0 14px;background:rgba(236,236,238,.96);border-bottom:1px solid rgba(0,0,0,.06)}
.hs-window-dot{width:12px;height:12px;border-radius:50%}
.hs-window-dot.is-close{background:#ff5f57}
.hs-window-dot.is-min{background:#febc2e}
.hs-window-dot.is-max{background:#28c840}
.hs-window-title{flex:1 1 auto;text-align:center;font-size:13px;font-weight:600;color:var(--hs-text);margin-right:44px}
.hs-window-body{padding:18px;overflow:auto}
.hs-dock{position:absolute;left:50%;bottom:12px;transform:translateX(-50%);height:66px;display:flex;align-items:center;gap:12px;padding:0 14px;background:rgba(255,255,255,.22);border-radius:18px;backdrop-filter:blur(24px) saturate(160%);box-shadow:var(--hs-shadow-2)}
.hs-dock-item{display:flex;align-items:center;justify-content:center;width:44px;height:44px;border-radius:12px;background:rgba(255,255,255,.35);font-size:22px;line-height:1}
</style>"#
        .to_string()
}
