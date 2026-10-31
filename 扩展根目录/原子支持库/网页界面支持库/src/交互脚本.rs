//! 桌面交互脚本：把窗口拖动、图标开窗、图标坞切换、最小化与启动器做成一段内联脚本。
//!
//! 脚本按声明拼装，接口地址由调用方给出；不含任何外部依赖，也不假设后端实现。

use crate::业务实现::{取对象文本, 取文本参数, 解析对象参数};
use crate::编号与码面::错误码;

const 缺省窗口接口: &str = "/接口/窗口";

const 脚本模板: &str = r#"<script>
(function(){
  var 窗口接口 = '{{窗口接口}}';
  var 层级 = 200;
  function 全部(选择器, 根){ return Array.prototype.slice.call((根||document).querySelectorAll(选择器)); }
  function 取层(){ return document.getElementById('hs-win-layer') || document.querySelector('.hs-desk'); }
  function 时钟(){
    var 现在 = new Date();
    var 时 = 现在.getHours(), 分 = 现在.getMinutes();
    var 文本 = '周' + '日一二三四五六'.charAt(现在.getDay()) + ' ' + (时<10?'0':'') + 时 + ':' + (分<10?'0':'') + 分;
    全部('[data-clock]').forEach(function(节点){ 节点.textContent = 文本; });
  }
  function 运行点(应用键, 存在){
    全部('.hs-dock-item[data-app="' + 应用键 + '"]').forEach(function(节点){
      var 点 = 节点.querySelector('.hs-dock-dot');
      if(存在 && !点){ var 新点 = document.createElement('i'); 新点.className = 'hs-dock-dot'; 节点.appendChild(新点); }
      if(!存在 && 点){ 点.remove(); }
    });
  }
  function 找窗口(应用键){ return document.querySelector('.hs-win[data-win="' + 应用键 + '"]'); }
  function 激活(窗口){
    if(!窗口){ return; }
    全部('.hs-win').forEach(function(项){ 项.classList.remove('is-active'); });
    窗口.classList.add('is-active');
    窗口.classList.remove('is-minimized');
    层级 += 1;
    窗口.style.zIndex = 层级;
  }
  function 打开(应用键){
    var 已有 = 找窗口(应用键);
    if(已有){ 激活(已有); return; }
    fetch(窗口接口 + (窗口接口.indexOf('?') >= 0 ? '&' : '?') + '应用=' + encodeURIComponent(应用键))
      .then(function(应答){ if(!应答.ok){ throw new Error('窗口接口返回 ' + 应答.status); } return 应答.text(); })
      .then(function(片段){
        取层().insertAdjacentHTML('beforeend', 片段);
        运行点(应用键, true);
        激活(找窗口(应用键));
      })
      .catch(function(错误){
        alert('打开失败：' + 错误.message);
      });
  }
  function 关闭(窗口){
    if(!窗口){ return; }
    var 应用键 = 窗口.getAttribute('data-win');
    窗口.remove();
    if(!找窗口(应用键)){ 运行点(应用键, false); }
  }
  document.addEventListener('click', function(事件){
    var 动作 = 事件.target.closest('[data-win-action]');
    if(动作){
      事件.stopPropagation();
      var 窗口 = 动作.closest('.hs-win');
      var 名称 = 动作.getAttribute('data-win-action');
      if(名称 === '关闭'){ 关闭(窗口); }
      if(名称 === '最小化'){ 窗口.classList.add('is-minimized'); }
      if(名称 === '最大化'){
        窗口.classList.toggle('is-max');
        if(窗口.classList.contains('is-max')){
          窗口.dataset.旧样式 = 窗口.getAttribute('style') || '';
          窗口.style.cssText = 'left:0;top:30px;width:100%;height:calc(100vh - 108px);z-index:' + 层级;
        } else {
          窗口.setAttribute('style', 窗口.dataset.旧样式 || '');
        }
      }
      return;
    }
    var 图标 = 事件.target.closest('.hs-icon');
    if(图标){
      全部('.hs-icon').forEach(function(项){ 项.classList.remove('is-selected'); });
      图标.classList.add('is-selected');
      return;
    }
    var 坞项 = 事件.target.closest('.hs-dock-item');
    if(坞项){
      var 键 = 坞项.getAttribute('data-app');
      var 窗 = 找窗口(键);
      if(窗 && 窗.classList.contains('is-minimized')){ 激活(窗); }
      else if(窗 && 窗.classList.contains('is-active')){ 窗.classList.add('is-minimized'); }
      else if(窗){ 激活(窗); }
      else { 打开(键); }
      return;
    }
    var 启动项 = 事件.target.closest('.hs-launchpad-item');
    if(启动项){
      关闭启动器();
      打开(启动项.getAttribute('data-app'));
      return;
    }
    var 窗面 = 事件.target.closest('.hs-win');
    if(窗面){ 激活(窗面); }
  });
  document.addEventListener('dblclick', function(事件){
    var 图标 = 事件.target.closest('.hs-icon');
    if(图标){ 打开(图标.getAttribute('data-app')); }
  });
  var 拖动中 = null;
  document.addEventListener('mousedown', function(事件){
    var 条 = 事件.target.closest('[data-drag]');
    if(!条 || 事件.target.closest('[data-win-action]')){ return; }
    var 窗 = 条.closest('.hs-win');
    var 起横 = 事件.clientX, 起纵 = 事件.clientY;
    var 左 = parseInt(窗.style.left || '0', 10), 上 = parseInt(窗.style.top || '0', 10);
    拖动中 = function(移动事件){
      窗.style.left = Math.max(0, 左 + 移动事件.clientX - 起横) + 'px';
      窗.style.top = Math.max(30, 上 + 移动事件.clientY - 起纵) + 'px';
    };
    激活(窗);
    事件.preventDefault();
  });
  document.addEventListener('mousemove', function(事件){ if(拖动中){ 拖动中(事件); } });
  document.addEventListener('mouseup', function(){ 拖动中 = null; });
  function 打开启动器(){
    var 面板 = document.getElementById('hs-launchpad');
    if(面板){ 面板.hidden = false; }
  }
  function 关闭启动器(){
    var 面板 = document.getElementById('hs-launchpad');
    if(面板){ 面板.hidden = true; }
  }
  document.addEventListener('keydown', function(事件){
    if(事件.key === 'F4'){ 事件.preventDefault(); 打开启动器(); }
    if(事件.key === 'Escape'){ 关闭启动器(); }
  });
  var 启动面板 = document.getElementById('hs-launchpad');
  if(启动面板){
    启动面板.addEventListener('click', function(事件){ if(事件.target === 启动面板){ 关闭启动器(); } });
    var 搜索框 = 启动面板.querySelector('[data-launchpad-search]');
    if(搜索框){
      搜索框.addEventListener('input', function(){
        var 关键字 = 搜索框.value.trim().toLowerCase();
        全部('.hs-launchpad-item', 启动面板).forEach(function(项){
          var 名称 = (项.textContent || '').toLowerCase();
          项.style.display = (!关键字 || 名称.indexOf(关键字) >= 0) ? '' : 'none';
        });
      });
    }
  }
  全部('[data-menu]').forEach(function(菜单){
    var 菜单键 = 菜单.getAttribute('data-menu') || '';
    if(菜单键 === '启动器'){ 菜单.addEventListener('click', 打开启动器); }
    else if(菜单键.charAt(0) === '/'){ 菜单.addEventListener('click', function(){ location.href = 菜单键; }); }
  });
  时钟();
  setInterval(时钟, 30000);
  /* ===== 图标网格摆放：照 V3 图标网格模型的算法（中档 88×92，间距 4，留白 18/14，右对齐起点，列优先从最右列往下） ===== */
  var 图标宽 = 88, 图标高 = 92, 格间距 = 4;
  var 格宽 = 图标宽 + 格间距, 格高 = 图标高 + 格间距;
  var 留白X = 18, 留白Y = 14;
  function 布局图标网格(){
    var 层 = document.querySelector('.hs-icon-layer');
    if(!层){ return; }
    var 项表 = [].slice.call(document.querySelectorAll('.hs-icon'));
    if(!项表.length){ return; }
    var 可用宽 = 层.clientWidth - 留白X * 2;
    var 可用高 = 层.clientHeight - 留白Y * 2;
    var 列数 = Math.max(1, Math.floor(可用宽 / 格宽));
    var 行数 = Math.max(1, Math.floor(可用高 / 格高));
    var 起X = Math.max(留白X, 层.clientWidth - 留白X - ((列数 - 1) * 格宽 + 图标宽));
    for(var i = 0; i < 项表.length; i++){
      var 列 = 列数 - 1 - Math.floor(i / 行数);
      var 行 = i % 行数;
      if(列 < 0){ 列 = 0; }
      项表[i].style.left = (起X + 列 * 格宽) + 'px';
      项表[i].style.top = (留白Y + 行 * 格高) + 'px';
    }
  }
  /* ===== Dock 放大：照 V3 磁吸参数（基准 48、最大 1.58 倍、影响范围 120px） ===== */
  var 坞基准 = 48, 坞最大倍 = 1.58, 坞范围 = 120;
  function 绑定坞放大(){
    var 坞 = document.querySelector('.hs-dock');
    if(!坞){ return; }
    var 项表 = [].slice.call(坞.querySelectorAll('.hs-dock-item'));
    function 复位(){ 项表.forEach(function(项){ 项.style.transform = ''; }); }
    坞.addEventListener('mousemove', function(事件){
      项表.forEach(function(项){
        var 框 = 项.getBoundingClientRect();
        var 距 = Math.abs(事件.clientX - (框.left + 框.width / 2));
        var 比例 = 距 > 坞范围 ? 0 : 1 - 距 / 坞范围;
        var 倍 = 1 + (坞最大倍 - 1) * 比例;
        项.style.transform = 'translateY(' + (-6 * 比例).toFixed(2) + 'px) scale(' + 倍.toFixed(3) + ')';
      });
    });
    坞.addEventListener('mouseleave', 复位);
  }
  布局图标网格();
  绑定坞放大();
  window.addEventListener('resize', 布局图标网格);
})();
</script>\"#;

fn 清理接口文本(原文: &str) -> String {
    let 可用 = 原文
        .chars()
        .filter(|字符| {
            字符.is_alphanumeric() || matches!(字符, '/' | '-' | '_' | '?' | '&' | '=' | '.')
        })
        .collect::<String>();
    if 可用.starts_with('/') {
        可用
    } else {
        缺省窗口接口.to_string()
    }
}

/// 按桌面配置生成内联脚本文本。
pub(crate) fn 脚本文本(桌面配置: &serde_json::Value) -> String {
    let 接口原文 = 取对象文本(桌面配置, "窗口接口");
    let 接口文本 = if 接口原文.is_empty() {
        缺省窗口接口.to_string()
    } else {
        清理接口文本(&接口原文)
    };
    脚本模板.replace("{{窗口接口}}", &接口文本)
}

/// 4923 渲染桌面交互脚本：参数为脚本配置 JSON，返回可内联的 script 片段。
pub(crate) fn 渲染桌面交互脚本(参数表: &[&[u8]]) -> Result<(u32, Vec<u8>), u32> {
    let 脚本配置原文 = 取文本参数(参数表, 0)?;
    let 脚本配置 = 解析对象参数(&脚本配置原文)?;
    Ok((4, 脚本文本(&脚本配置).into_bytes()))
}

#[allow(dead_code)]
fn 校验错误码可用() -> u32 {
    错误码::参数不合法
}
