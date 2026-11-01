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
