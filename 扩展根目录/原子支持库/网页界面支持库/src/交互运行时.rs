//! 交互运行时：只做「声明了才生效」的通用交互，不含任何产品语义。
//!
//! 页面里出现悬浮层、窗口或可选图标时，才把对应脚本附在整页末尾；
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

/// 窗口脚本：关闭、最小化（收起为标题栏）、最大化（铺满画布）、点击置顶与聚焦、拖动；
/// 能否动作全看窗口节点上的 data-* 开关，脚本不带产品语义。
pub(crate) const 窗口脚本: &str = r#"<script>(function(){
function 宿主(元素){return 元素.closest('[data-window-port]')||元素}
function 找窗(标识){return document.querySelector('[data-window="'+标识+'"]')}
function 置顶(元素){var 同级=Array.prototype.slice.call(元素.parentElement.children).filter(function(节点){return 节点.hasAttribute('data-window-port')});同级.sort(function(前窗,后窗){return Number(前窗.style.zIndex||0)-Number(后窗.style.zIndex||0)});同级.filter(function(节点){return 节点!==元素}).concat([元素]).forEach(function(节点,索引){节点.style.zIndex=String(索引+2)})}
function 聚焦(壳){document.querySelectorAll('[data-window-port]').forEach(function(节点){节点.classList.toggle('is-focus',节点===壳)})}
function 收起(窗){窗.classList.add('is-hidden');宿主(窗).hidden=true}
function 展开(窗){窗.classList.remove('is-hidden');窗.classList.remove('is-min');宿主(窗).hidden=false;置顶(宿主(窗));聚焦(宿主(窗))}
function 铺满(窗){var 壳=宿主(窗);if(壳.classList.contains('is-max')){壳.classList.remove('is-max');壳.style.left=壳.getAttribute('data-原左')||'';壳.style.top=壳.getAttribute('data-原上')||'';壳.style.width=壳.getAttribute('data-原宽')||'';壳.style.height=壳.getAttribute('data-原高')||''}else{壳.setAttribute('data-原左',壳.style.left);壳.setAttribute('data-原上',壳.style.top);壳.setAttribute('data-原宽',壳.style.width);壳.setAttribute('data-原高',壳.style.height);壳.classList.add('is-max')}}
document.addEventListener('click',function(事件){
var 关闭=事件.target.closest('[data-window-close]');
if(关闭){事件.preventDefault();var 窗=找窗(关闭.getAttribute('data-window-close'));if(窗){收起(窗)}return}
var 最小化=事件.target.closest('[data-window-min]');
if(最小化){事件.preventDefault();var 窗=找窗(最小化.getAttribute('data-window-min'));if(窗){var 收=窗.classList.toggle('is-min');宿主(窗).classList.toggle('is-min',收)}return}
var 最大化=事件.target.closest('[data-window-max]');
if(最大化){事件.preventDefault();var 窗=找窗(最大化.getAttribute('data-window-max'));if(窗){铺满(窗);置顶(宿主(窗));聚焦(宿主(窗))}return}
var 触发=事件.target.closest('[data-window-open]');if(!触发){return}
var 目标=找窗(触发.getAttribute('data-window-open'));if(!目标){return}
事件.preventDefault();展开(目标);
var 浮层=触发.closest('[data-overlay]');if(浮层){浮层.classList.add('is-hidden')}
});
document.addEventListener('mousedown',function(事件){
if(事件.button!==0){return}var 窗=事件.target.closest('[data-window]');if(!窗){return}
置顶(宿主(窗));聚焦(宿主(窗));
if(窗.getAttribute('data-movable')!=='1'){return}
if(!事件.target.closest('.hs-tree-window-bar')||事件.target.closest('button')){return}
var 壳=宿主(窗);if(getComputedStyle(壳).position!=='absolute'||壳.classList.contains('is-max')){return}
var 起点横坐标=事件.clientX,起点纵坐标=事件.clientY,原左=壳.offsetLeft,原上=壳.offsetTop;
function 移动(移动事件){var 范围=壳.parentElement.getBoundingClientRect();壳.style.left=Math.max(40-壳.offsetWidth,Math.min(范围.width-40,原左+移动事件.clientX-起点横坐标))+'px';壳.style.top=Math.max(0,Math.min(范围.height-32,原上+移动事件.clientY-起点纵坐标))+'px'}
function 松开(){document.removeEventListener('mousemove',移动);document.removeEventListener('mouseup',松开);window.removeEventListener('blur',松开)}
document.addEventListener('mousemove',移动);document.addEventListener('mouseup',松开);window.addEventListener('blur',松开);事件.preventDefault();
});
var 首窗=null;document.querySelectorAll('[data-window-port]').forEach(function(节点){if(!首窗&&!节点.hidden){首窗=节点}});if(首窗){首窗.classList.add('is-focus')}
})();</script>"#;

/// 选中脚本：点了就选中，同一片区（画布或网格）里只留一个。
pub(crate) const 选中脚本: &str = r#"<script>(function(){
document.addEventListener('click',function(事件){
var 目标=事件.target.closest('[data-select]');if(!目标){return}
var 片区=目标.closest('.hs-tree-canvas')||目标.closest('.hs-tree-grid')||document.body;
片区.querySelectorAll('[data-select]').forEach(function(节点){节点.classList.toggle('is-selected',节点===目标)});
});
})();</script>"#;

/// 放大脚本：容器声明了 `放大` 才生效。鼠标横向位置决定邻域缩放，
/// 曲线是 cos² 平滑衰减（距离 0 处到峰值，到半径处回到 1），缩放靠 transform + 外边距让邻居让位。
pub(crate) const 放大脚本: &str = r#"<script>(function(){
document.querySelectorAll('[data-magnify]').forEach(function(容器){
var 参数=容器.getAttribute('data-magnify').split(',');
var 峰值=Number(参数[0])||1;if(峰值<=1){return}
var 半径=Number(参数[1])||120;
var 项表=Array.prototype.slice.call(容器.querySelectorAll('.hs-tree-icon'));
if(!项表.length){return}
var 基准宽=项表.map(function(项){return 项.offsetWidth||1});
var 当前=项表.map(function(){return 1});
var 鼠横=null,平滑=null,帧号=0;
function 目标缩放(索引,横){
  if(横===null){return 1}
  var 框=项表[索引].getBoundingClientRect();
  var 距=Math.abs(横-(框.left+框.width/2));
  if(距>=半径){return 1}
  var 余弦=Math.cos((距/半径)*Math.PI/2);
  return 1+(峰值-1)*余弦*余弦;
}
function 应用(索引,值){项表[索引].style.transform='scale('+值+')';var 余=((值-1)*基准宽[索引]/2);项表[索引].style.marginLeft=余+'px';项表[索引].style.marginRight=余+'px'}
function 跑(){
  帧号=0;
  if(鼠横===null){平滑=null}else if(平滑===null){平滑=鼠横}else{平滑+= (鼠横-平滑)*0.3}
  var 在动=false;
  项表.forEach(function(项,索引){
    var 想要=目标缩放(索引,平滑);
    var 现值=当前[索引]+(想要-当前[索引])*0.28;
    if(Math.abs(现值-想要)<0.001){现值=想要}
    if(Math.abs(现值-当前[索引])>0.0004){应用(索引,现值);当前[索引]=现值}
    if(Math.abs(现值-1)>0.001||(平滑!==null&&想要>1)){在动=true}
  });
  if(在动||鼠横!==null){帧号=requestAnimationFrame(跑)}
}
容器.addEventListener('mousemove',function(事件){鼠横=事件.clientX;if(!帧号){帧号=requestAnimationFrame(跑)}});
容器.addEventListener('mouseleave',function(){鼠横=null;if(!帧号){帧号=requestAnimationFrame(跑)}});
});
})();</script>"#;

/// 筛选脚本：输入框按文字筛、分类按钮按 `筛选值` 筛，都作用在同一片被筛容器上。
pub(crate) const 筛选脚本: &str = r#"<script>(function(){
function 找片(名字){return document.querySelector('[data-filter-scope="'+名字+'"]')}
function 应用(片,词,类){片.querySelectorAll('[data-filter-value]').forEach(function(项){
var 命中=true;
var 值=项.getAttribute('data-filter-value')||'';
if(词){命中=(项.textContent||'').indexOf(词)>=0}
if(命中&&类&&类!=='全部'){命中=(值===类)}
项.style.display=命中?'':'none';
});}
document.querySelectorAll('[data-filter-target]').forEach(function(输入){
输入.addEventListener('input',function(){
var 片=找片(输入.getAttribute('data-filter-target'));if(!片){return}
片.setAttribute('data-词',输入.value.trim());
应用(片,片.getAttribute('data-词')||'',片.getAttribute('data-类')||'');
});});
document.addEventListener('click',function(事件){
var 按钮=事件.target.closest('[data-filter-cat]');if(!按钮){return}
事件.preventDefault();
var 目标=按钮.closest('[data-filter-scope]');
if(!目标){return}
var 类=按钮.getAttribute('data-filter-cat')||'';
目标.setAttribute('data-类',类);
目标.querySelectorAll('[data-filter-cat]').forEach(function(钮){钮.classList.toggle('is-selected',钮===按钮)});
应用(目标,目标.getAttribute('data-词')||'',类);
});
})();</script>"#;
