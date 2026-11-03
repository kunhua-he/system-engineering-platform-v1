//! 右键菜单：任何节点声明「右键菜单」就有菜单，菜单项只做四种通用动作。
pub(crate) const 右键菜单脚本: &str = r#"<script>(function(){
function 关闭(){var 旧=document.querySelector('.hs-menu');if(旧){旧.remove()}}
function 开(层,事件,项表){
 关闭();
 var 单=document.createElement('div');单.className='hs-menu';
 单.style.left=事件.clientX+'px';单.style.top=事件.clientY+'px';
 项表.forEach(function(项){
  var 行=document.createElement('div');行.className='hs-menu-item';行.textContent=项.文本||'';
  行.addEventListener('click',function(事件2){
   事件2.stopPropagation();关闭();
   if(项.打开窗口){var 窗=document.querySelector('[data-窗口="'+项.打开窗口+'"]');if(窗){窗.classList.remove('已隐藏');var 壳=窗.closest('[data-窗口壳]');if(壳){壳.hidden=false}}}
   if(项.切换显隐){var 目标=document.querySelector('[data-overlay="'+项.切换显隐+'"]');if(目标){目标.classList.toggle('已隐藏')}}
   if(项.打开地址){window.location.href=项.打开地址}
   if(项.提示&&window.hs提示){window.hs提示(项.提示)}
  });
  单.appendChild(行);
 });
 document.body.appendChild(单);
 var 框=单.getBoundingClientRect();
 if(框.right>window.innerWidth){单.style.left=(window.innerWidth-框.width-8)+'px'}
 if(框.bottom>window.innerHeight){单.style.top=(window.innerHeight-框.height-8)+'px'}
}
document.addEventListener('contextmenu',function(事件){
 var 宿主=事件.target.closest('[data-menu]');
 if(!宿主){return}
 var 项表;
 try{项表=JSON.parse(宿主.getAttribute('data-menu'))}catch(错){return}
 if(!Array.isArray(项表)||!项表.length){return}
 事件.preventDefault();开(宿主,事件,项表);
});
document.addEventListener('click',关闭);
document.addEventListener('scroll',关闭,true);
})();</script>"#;
