//! 拖放重排：同组元素可以互相拖动换位，换完把顺序写回容器的 data-order。
//! 顺序回传给谁、怎么存，底座不管 —— 只把顺序摆到 data-order，由取用方决定。
pub(crate) const 拖放脚本: &str = r#"<script>(function(){
function 组内项(组){return Array.prototype.slice.call(组.querySelectorAll('[data-draggable="1"]'))}
function 记顺序(组){
 组.setAttribute('data-order',组内项(组).map(function(项){return 项.getAttribute('data-drag-key')||''}).join(','));
 var 地址=组.getAttribute('data-order-url');
 if(地址&&window.fetch){
  fetch(地址,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',
   body:JSON.stringify({组:组.getAttribute('data-drop-group')||'',顺序:组.getAttribute('data-order')})}).catch(function(){});
 }
}
document.addEventListener('dragstart',function(事件){
 var 项=事件.target.closest('[data-draggable="1"]');
 if(!项){return}
 项.classList.add('拖动中');
 事件.dataTransfer.effectAllowed='move';
 事件.dataTransfer.setData('text/plain',项.getAttribute('data-drag-key')||'');
});
document.addEventListener('dragend',function(事件){
 var 项=事件.target.closest('[data-draggable="1"]');
 if(项){项.classList.remove('拖动中')}
 document.querySelectorAll('[data-drop-group]').forEach(function(组){组.classList.remove('放置目标')});
});
document.addEventListener('dragover',function(事件){
 var 组=事件.target.closest('[data-drop-group]');
 if(!组){return}
 事件.preventDefault();事件.dataTransfer.dropEffect='move';组.classList.add('放置目标');
 var 拖=document.querySelector('.拖动中');if(!拖){return}
 var 目标=事件.target.closest('[data-draggable="1"]');
 if(!目标||目标===拖){return}
 var 框=目标.getBoundingClientRect();
 var 之后=(事件.clientY-框.top)>框.height/2;
 目标.parentNode.insertBefore(拖,之后?目标.nextSibling:目标);
});
document.addEventListener('drop',function(事件){
 var 组=事件.target.closest('[data-drop-group]');
 if(!组){return}
 事件.preventDefault();组.classList.remove('放置目标');记顺序(组);
});
document.querySelectorAll('[data-drop-group]').forEach(function(组){
 组内项(组).forEach(function(项){
   项.setAttribute('draggable','true');
   if(!项.getAttribute('data-drag-key')){项.setAttribute('data-drag-key','项-'+(项.getAttribute('data-窗口壳')||项.textContent||'').slice(0,12))}
 });
});
})();</script>"#;
