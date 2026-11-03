//! 公共组件事件搬运；数据、选择和排序均由底座计算。
pub(crate) const 组件引导脚本: &str = r#"<script>(function(){
if(window.__组件事件就绪){return}window.__组件事件就绪=true;
var 请求队列={},单击定时=null,拖动来源=null,最近跟踪='';
function 交回操作(目标元素,操作名称,操作参数){
 var 句柄元素=目标元素.closest('[data-hs-h]');if(!句柄元素||typeof window.hs组件操作!=='function'){return Promise.resolve()}
 var 组件句柄=Number(句柄元素.getAttribute('data-hs-h'));
 var 请求内容={句柄:组件句柄,操作:操作名称,参数:操作参数};
 var 请求任务=(请求队列[组件句柄]||Promise.resolve()).catch(function(){}).then(function(){return window.hs组件操作(请求内容)});
 请求队列[组件句柄]=请求任务;return 请求任务;
}
function 取事件参数(目标元素){
 var 事件参数={},行元素=目标元素.closest('[data-hs-row]');
 var 表头元素=目标元素.closest('[data-hs-header-column]');if(表头元素){事件参数.列索引=Number(表头元素.getAttribute('data-hs-header-column'))}
 if(行元素){事件参数.表项索引=Number(行元素.getAttribute('data-hs-row'))}
 if(目标元素.hasAttribute('data-hs-edit-column')){事件参数.列索引=Number(目标元素.getAttribute('data-hs-edit-column'))}
 return 事件参数;
}
document.addEventListener('click',function(浏览事件){
 if(浏览事件.target.closest('input[data-hs-edit-row]')){return}
 var 目标元素=浏览事件.target.closest('[data-hs-op],[data-hs-event]');if(!目标元素){return}
 var 操作名称=目标元素.getAttribute('data-hs-op')||'记录事件',操作参数=取事件参数(目标元素);
 if(目标元素.hasAttribute('data-hs-key')){操作参数.键=目标元素.getAttribute('data-hs-key')}
 if(目标元素.hasAttribute('data-hs-page')){操作参数.页码=Number(目标元素.getAttribute('data-hs-page'))}
 if(目标元素.hasAttribute('data-排序升序')){操作参数.升序=目标元素.getAttribute('data-排序升序')==='true'}
 if(目标元素.hasAttribute('data-hs-event')){操作参数.事件名=目标元素.getAttribute('data-hs-event')}
 if(目标元素.matches('input[type=checkbox]')){操作参数.检查框状态=目标元素.checked}
 浏览事件.preventDefault();
 if(浏览事件.target.closest('[data-hs-event-double-op]')){clearTimeout(单击定时);单击定时=setTimeout(function(){交回操作(目标元素,操作名称,操作参数)},240)}
 else{交回操作(目标元素,操作名称,操作参数)}
});
document.addEventListener('dblclick',function(浏览事件){
 clearTimeout(单击定时);var 编辑元素=浏览事件.target.closest('[data-hs-event-double-op]');
 var 目标元素=编辑元素||浏览事件.target.closest('[data-hs-event-double]');if(!目标元素){return}
 浏览事件.preventDefault();var 操作参数=取事件参数(目标元素);操作参数.事件名='表项被激活';
 交回操作(目标元素,编辑元素?'进入编辑':'记录事件',操作参数);
});
document.addEventListener('contextmenu',function(浏览事件){
 var 目标元素=浏览事件.target.closest('[data-hs-event-context]');if(!目标元素){return}
 浏览事件.preventDefault();var 操作参数=取事件参数(目标元素);操作参数.事件名=目标元素.getAttribute('data-hs-event-context');交回操作(目标元素,'记录事件',操作参数);
});
document.addEventListener('mouseover',function(浏览事件){
 var 目标元素=浏览事件.target.closest('[data-hs-event-hover]');if(!目标元素||目标元素.contains(浏览事件.relatedTarget)){return}
 if(!目标元素.closest('table').classList.contains('热点跟踪')){return}
 var 跟踪标识=目标元素.closest('[data-hs-h]').getAttribute('data-hs-h')+':'+目标元素.getAttribute('data-hs-row');if(最近跟踪===跟踪标识){return}最近跟踪=跟踪标识;
 var 操作参数=取事件参数(目标元素);操作参数.事件名='表项跟踪';交回操作(目标元素,'记录事件',操作参数);
});
document.addEventListener('mouseout',function(浏览事件){var 目标元素=浏览事件.target.closest('[data-hs-event-hover]');if(!目标元素||目标元素.contains(浏览事件.relatedTarget)||!目标元素.closest('table').classList.contains('热点跟踪')){return}if(浏览事件.relatedTarget&&浏览事件.relatedTarget.closest&&浏览事件.relatedTarget.closest('[data-hs-event-hover]')){return}最近跟踪='';交回操作(目标元素,'记录事件',{事件名:'表项跟踪',表项索引:-1})});
function 提交编辑(输入元素){if(输入元素.__已经提交){return}输入元素.__已经提交=true;var 操作参数=取事件参数(输入元素);操作参数.标题=输入元素.value;交回操作(输入元素,'结束编辑',操作参数)}
document.addEventListener('change',function(浏览事件){var 输入元素=浏览事件.target.closest('input[data-hs-edit-row]');if(输入元素){提交编辑(输入元素)}});
document.addEventListener('keydown',function(浏览事件){
 var 输入元素=浏览事件.target.closest('input[data-hs-edit-row]');
 if(输入元素&&浏览事件.key==='Enter'){浏览事件.preventDefault();提交编辑(输入元素)}
 if(输入元素&&浏览事件.key==='Escape'){浏览事件.preventDefault();输入元素.__已经提交=true;交回操作(输入元素,'取消编辑',{})}
 if(!输入元素&&浏览事件.key==='Enter'){var 行元素=浏览事件.target.closest('[data-hs-event-double]');if(行元素){var 操作参数=取事件参数(行元素);操作参数.事件名='表项被激活';交回操作(行元素,'记录事件',操作参数)}}
});
document.addEventListener('dragstart',function(浏览事件){
 var 表头元素=浏览事件.target.closest('th[draggable="true"]');if(!表头元素){return}
 拖动来源=表头元素;浏览事件.dataTransfer.setData('text/plain',表头元素.getAttribute('data-hs-column'));浏览事件.dataTransfer.effectAllowed='move';
});
document.addEventListener('dragover',function(浏览事件){if(拖动来源&&浏览事件.target.closest('th[data-hs-column]')){浏览事件.preventDefault()}});
document.addEventListener('drop',function(浏览事件){
 var 表头元素=浏览事件.target.closest('th[data-hs-column]');if(!表头元素||!拖动来源||表头元素.closest('table')!==拖动来源.closest('table')){return}
 浏览事件.preventDefault();交回操作(表头元素,'移动列',{列索引:Number(拖动来源.getAttribute('data-hs-column')),目标位置:Number(表头元素.getAttribute('data-hs-column'))});拖动来源=null;
});
document.addEventListener('dragend',function(){拖动来源=null});
document.addEventListener('pointermove',function(浏览事件){
 if(浏览事件.buttons){return}
 var 表头元素=浏览事件.target.closest('th[data-hs-header-column]');
 if(!表头元素){document.body.style.cursor='';return}
 var 手势=取拖动手势(表头元素,浏览事件);
 表头元素.style.cursor=手势==='列宽'?'col-resize':(手势==='行高'?'row-resize':'');
});
function 取拖动手势(表头元素,浏览事件){
 if(浏览事件.target.closest('button,input,a,[data-hs-op]')){return ''}
 var 矩形=表头元素.getBoundingClientRect();
 if(矩形.right-浏览事件.clientX<=6){return '列宽'}
 if(矩形.bottom-浏览事件.clientY<=6){return '行高'}
 return '';
}
document.addEventListener('pointerdown',function(浏览事件){
 var 表头元素=浏览事件.target.closest('th[data-hs-header-column]');if(!表头元素||浏览事件.button!==0){return}
 var 手势=取拖动手势(表头元素,浏览事件);if(!手势){return}
 浏览事件.preventDefault();浏览事件.stopPropagation();
 var 表头矩形=表头元素.getBoundingClientRect(),表格元素=表头元素.closest('table');
 var 起X=浏览事件.clientX,起Y=浏览事件.clientY,起宽=表头矩形.width;
 var 首行元素=表格元素.querySelector('tbody tr');
 var 起高=Math.round(首行元素?首行元素.getBoundingClientRect().height:表头矩形.height);
 var 列组=表格元素.querySelectorAll('colgroup col'),列索引=[...表格元素.querySelectorAll('thead th')].indexOf(表头元素);
 if(手势==='列宽'){
  document.body.style.cursor='col-resize';
  var 列宽值=Math.round(起宽);
  function 拖动列宽(移动事件){列宽值=Math.max(40,Math.min(2000,Math.round(起宽+移动事件.clientX-起X)));表头元素.style.width=列宽值+'px';if(列组[列索引]){列组[列索引].style.width=列宽值+'px'}}
  function 结束列宽(){document.removeEventListener('pointermove',拖动列宽);document.removeEventListener('pointerup',结束列宽);document.removeEventListener('pointercancel',结束列宽);document.body.style.cursor='';表头元素.style.cursor='';交回操作(表头元素,'设置列宽',{列索引:Number(表头元素.getAttribute('data-hs-header-column')),列宽:列宽值})}
  document.addEventListener('pointermove',拖动列宽);document.addEventListener('pointerup',结束列宽);document.addEventListener('pointercancel',结束列宽);
  return;
 }
 document.body.style.cursor='row-resize';表格元素.setAttribute('data-固定行高','true');
 var 行高值=Math.min(200,Math.max(20,起高));
 function 拖动行高(移动事件){行高值=Math.min(200,Math.max(20,Math.round(起高+移动事件.clientY-起Y)));表格元素.style.setProperty('--表格行高',行高值+'px')}
 function 结束行高(){document.removeEventListener('pointermove',拖动行高);document.removeEventListener('pointerup',结束行高);document.removeEventListener('pointercancel',结束行高);document.body.style.cursor='';交回操作(表头元素,'设置行高',{行高:行高值})}
 document.addEventListener('pointermove',拖动行高);document.addEventListener('pointerup',结束行高);document.addEventListener('pointercancel',结束行高);
});
function 同步呈现(范围元素){
 var 查找范围=范围元素.querySelectorAll?范围元素:document;
 查找范围.querySelectorAll('[data-hs-scroll-target]').forEach(function(目标元素){目标元素.removeAttribute('data-hs-scroll-target');目标元素.scrollIntoView({block:'nearest',inline:'nearest'})});
 查找范围.querySelectorAll('input[data-hs-edit-row]').forEach(function(输入元素){if(!输入元素.__已经聚焦){输入元素.__已经聚焦=true;输入元素.focus();输入元素.select()}});
}
new MutationObserver(function(记录列表){记录列表.forEach(function(记录项){记录项.addedNodes.forEach(function(新增元素){if(新增元素.nodeType===1){同步呈现(新增元素)}})})}).observe(document.documentElement,{childList:true,subtree:true});
同步呈现(document);
})();</script>"#;
