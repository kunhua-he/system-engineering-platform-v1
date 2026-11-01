//! 交互运行时：只做「声明了才生效」的通用显隐切换，不含任何产品语义。
//!
//! 页面里出现悬浮层或「切换显隐」声明时，才把这段脚本附在整页末尾；
//! 所有目标都由 data-* 属性给出，脚本不拼接任何用户文本。

pub(crate) const 显隐切换脚本: &str = r#"<script>(function(){
function 切换(标识){var 层=document.querySelector('[data-overlay="'+标识+'"]');if(!层){return}if(层.classList.contains('is-hidden')){层.classList.remove('is-hidden')}else{层.classList.add('is-hidden')}}
document.addEventListener('click',function(事件){var 触发=事件.target.closest('[data-toggle]');if(!触发){return}事件.preventDefault();切换(触发.getAttribute('data-toggle'))});
document.addEventListener('keydown',function(事件){
var 层=document.querySelector('[data-key="'+事件.key+'"]');if(!层){return}事件.preventDefault();
if(层.classList.contains('is-hidden')){层.classList.remove('is-hidden')}else{层.classList.add('is-hidden')}
});
document.querySelectorAll('[data-overlay]').forEach(function(层){层.addEventListener('click',function(事件){if(事件.target===层){层.classList.add('is-hidden')}})});
})();</script>"#;

/// 窗口脚本：标题栏拖动、点击置顶、关闭；无产品路由或配色。
pub(crate) const 窗口脚本: &str = r#"<script>(function(){
function 宿主(元素){return 元素.closest('[data-window-port]')||元素}
function 置顶(元素){var 同级=Array.from(元素.parentElement.children).filter(function(节点){return 节点.hasAttribute('data-window-port')});同级.sort(function(前窗,后窗){return Number(前窗.style.zIndex||0)-Number(后窗.style.zIndex||0)});同级.filter(function(节点){return 节点!==元素}).concat([元素]).forEach(function(节点,索引){节点.style.zIndex=String(索引+2)})}
document.addEventListener('click',function(事件){
var 关闭=事件.target.closest('[data-window-close]');
if(关闭){事件.preventDefault();var 窗=document.querySelector('[data-window="'+关闭.getAttribute('data-window-close')+'"]');if(窗){窗.classList.add('is-hidden');宿主(窗).hidden=true}return}
var 触发=事件.target.closest('[data-window-open]');if(!触发){return}
var 目标=document.querySelector('[data-window="'+触发.getAttribute('data-window-open')+'"]');
if(!目标){return}事件.preventDefault();目标.classList.remove('is-hidden');宿主(目标).hidden=false;置顶(宿主(目标));
var 浮层=触发.closest('[data-overlay]');if(浮层){浮层.classList.add('is-hidden')}
});
document.addEventListener('mousedown',function(事件){
if(事件.button!==0){return}var 窗=事件.target.closest('[data-window]');if(!窗){return}
置顶(宿主(窗));var 条=事件.target.closest('.hs-tree-window-bar');
if(!条||事件.target.closest('button')){return}
var 壳=宿主(窗);if(getComputedStyle(壳).position!=='absolute'){return}
var 起点横坐标=事件.clientX,起点纵坐标=事件.clientY,原左=壳.offsetLeft,原上=壳.offsetTop;
function 移动(移动事件){var 范围=壳.parentElement.getBoundingClientRect();壳.style.left=Math.max(40-壳.offsetWidth,Math.min(范围.width-40,原左+移动事件.clientX-起点横坐标))+'px';壳.style.top=Math.max(0,Math.min(范围.height-32,原上+移动事件.clientY-起点纵坐标))+'px'}
function 松开(){document.removeEventListener('mousemove',移动);document.removeEventListener('mouseup',松开);window.removeEventListener('blur',松开)}
document.addEventListener('mousemove',移动);document.addEventListener('mouseup',松开);window.addEventListener('blur',松开);事件.preventDefault();
});
})();</script>"#;
