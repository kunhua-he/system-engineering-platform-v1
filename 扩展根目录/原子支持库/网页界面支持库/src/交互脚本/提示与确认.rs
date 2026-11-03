//! 轻提示与确认层：写操作的回执与不可逆操作的前置确认，都靠声明挂开关。
//! 页面只给文案与一个 data-* 钩子，脚本不认识任何业务。
pub(crate) const 提示脚本: &str = r#"<script>(function(){
function 容器(){
 var 层=document.querySelector('.hs-toast-layer');
 if(!层){层=document.createElement('div');层.className='hs-toast-layer';document.body.appendChild(层)}
 return 层;
}
function 提示(文本){
 if(!文本){return}
 var 层=容器();var 条=document.createElement('div');条.className='hs-toast';条.textContent=文本;
 层.appendChild(条);
 setTimeout(function(){条.classList.add('已淡出');setTimeout(function(){条.remove()},260)},2200);
}
window.hs提示=提示;
document.addEventListener('click',function(事件){
 var 触发=事件.target.closest('[data-toast]');
 if(触发){提示(触发.getAttribute('data-toast'))}
});
})();</script>"#;

pub(crate) const 确认脚本: &str = r#"<script>(function(){
function 弹层(文案,应答){
 var 层=document.createElement('div');层.className='hs-confirm-layer';
 var 盒=document.createElement('div');盒.className='hs-confirm';
 var 字=document.createElement('div');字.className='hs-confirm-text';字.textContent=文案||'确定要执行这个操作吗？';
 var 排=document.createElement('div');排.className='hs-confirm-actions';
 var 取消=document.createElement('button');取消.type='button';取消.className='hs-button';取消.textContent='取消';
 var 确定=document.createElement('button');确定.type='button';确定.className='hs-button hs-button-primary';确定.textContent='确定';
 取消.addEventListener('click',function(){层.remove();应答(false)});
 确定.addEventListener('click',function(){层.remove();应答(true)});
 排.appendChild(取消);排.appendChild(确定);盒.appendChild(字);盒.appendChild(排);层.appendChild(盒);
 层.addEventListener('click',function(事件){if(事件.target===层){层.remove();应答(false)}});
 document.body.appendChild(层);
}
document.addEventListener('click',function(事件){
 var 触发=事件.target.closest('[data-confirm]');
 if(!触发||触发.getAttribute('data-已确认')==='1'){return}
 事件.preventDefault();事件.stopPropagation();
 弹层(触发.getAttribute('data-confirm'),function(同意){
  if(!同意){return}
  触发.setAttribute('data-已确认','1');
  触发.click();
  setTimeout(function(){触发.removeAttribute('data-已确认')},0);
 });
},true);
})();</script>"#;
