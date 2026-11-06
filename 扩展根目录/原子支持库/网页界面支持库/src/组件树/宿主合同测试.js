const 断言=require('node:assert/strict');
const 虚拟机=require('node:vm');
const 页面=require('node:fs').readFileSync(0,'utf8');
const 期望地址=process.argv[1]||'/接口/调用';
const 脚本列表=[...页面.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(匹配项=>匹配项[1]);
for(const 脚本文本 of 脚本列表){new 虚拟机.Script(脚本文本)}
const 宿主正文=脚本列表.find(脚本文本=>脚本文本.includes('window.hs组件操作=function'));
断言.ok(宿主正文,'整页应注入宿主');
let 请求记录=[],替换记录=[],提示元素=null;
const 新组件={querySelector(){return {focus(){}}}};
const 旧组件={replaceWith(组件元素){替换记录.push(组件元素)}};
const 文档={querySelector(选择器){return 选择器.startsWith('[data-hs-h=')?旧组件:提示元素},createElement(){return {setAttribute(){},firstElementChild:新组件}},body:{appendChild(页面元素){提示元素=页面元素}}};
const 环境={window:{},document:文档,fetch:async(请求地址,请求选项)=>{请求记录.push({请求地址,请求选项});return {ok:true,status:200,json:async()=>({成功:true,值:[{类型标签:4,值:JSON.stringify({句柄组:[],片段:'<div>更新</div>'})}]})}}};
虚拟机.createContext(环境);虚拟机.runInContext(宿主正文,环境);
(async()=>{
 await 环境.window.hs组件操作({句柄:847362,操作:'排序',参数:{键:'销量',升序:true}});
 断言.equal(请求记录[0].请求地址,期望地址);
 断言.equal(请求记录[0].请求选项.method,'POST');
 断言.deepEqual(JSON.parse(请求记录[0].请求选项.body),{编号:4929,命名值:{组件句柄:847362,操作名:'排序',参数原文:JSON.stringify({键:'销量',升序:true})}});
 断言.equal(替换记录.length,1);
 断言.equal(环境.window.__未刷新,1);
 const 成功信封=片段文本=>({成功:true,值:[{类型标签:4,值:JSON.stringify({句柄组:[],片段:片段文本})}]});
 for(const 失败样本 of [
  {ok:false,status:503,json:async()=>({})},
  {ok:true,json:async()=>({成功:false,错误:{错误码:4924,说明:'句柄无效'}})},
  {ok:true,json:async()=>({片段:'<div>旧合同</div>'})},
  {ok:true,json:async()=>({成功:true,值:[]})},
  {ok:true,json:async()=>({成功:true,值:[{类型标签:1,值:'10'}]})},
  {ok:true,json:async()=>({成功:true,值:[{类型标签:4,值:'非JSON'}]})},
  {ok:true,json:async()=>成功信封('')},
  {ok:true,json:async()=>{throw new Error('响应损坏')}}
 ]){
  环境.fetch=async()=>失败样本;
  await 断言.rejects(环境.window.hs组件操作({句柄:847362,操作:'排序',参数:{}}));
  断言.equal(提示元素.hidden,false);断言.match(提示元素.textContent,/组件操作失败/);
  断言.equal(替换记录.length,1,'失败不能替换页面');
 }
 环境.fetch=async()=>{throw new Error('网络失败')};
 await 断言.rejects(环境.window.hs组件操作({句柄:847362,操作:'排序',参数:{}}));
 断言.match(提示元素.textContent,/网络失败/);
 环境.fetch=async()=>({ok:true,json:async()=>成功信封('')});
 const 事件回执=await 环境.window.hs组件操作({句柄:847362,操作:'记录事件',参数:{事件名:'表项跟踪'}});
 断言.equal(事件回执.片段,'');断言.equal(替换记录.length,1,'纯记录事件不重绘');
 环境.fetch=async()=>({ok:true,json:async()=>成功信封('<div>恢复</div>')});
 await 环境.window.hs组件操作({句柄:847362,操作:'翻页',参数:{页码:2}});
 断言.equal(提示元素.hidden,true);断言.equal(替换记录.length,2);
 const 事件监听={},事件序列=[];
 let 在途数量=0,最大在途=0;
 const 事件环境={window:{hs组件操作:async 请求内容=>{事件序列.push(请求内容);在途数量++;最大在途=Math.max(最大在途,在途数量);await new Promise(完成回调=>setImmediate(完成回调));在途数量--;if(请求内容.操作==='排序'){throw new Error('排序失败')}}},Promise,clearTimeout,setTimeout,MutationObserver:class{observe(){}},document:{addEventListener(事件名称,回调函数){事件监听[事件名称]=回调函数},querySelectorAll(){return []},documentElement:{}}};
 虚拟机.createContext(事件环境);
 虚拟机.runInContext(脚本列表.find(脚本文本=>脚本文本.includes('function 交回操作')),事件环境);
 function 产生点击(操作名称){
  const 点击元素={closest(选择器){return 选择器==='[data-hs-h]'?{getAttribute(){return '847362'}}:null},getAttribute(属性名称){return 属性名称==='data-hs-op'?操作名称:null},hasAttribute(){return false},matches(){return false}};
  事件监听.click({target:{closest(选择器){return 选择器==='[data-hs-op],[data-hs-event]'?点击元素:null}},preventDefault(){}});
 }
 产生点击('排序');产生点击('翻页');
 await new Promise(完成回调=>setTimeout(完成回调,20));
 断言.equal(最大在途,1);断言.deepEqual(事件序列.map(请求内容=>请求内容.操作),['排序','翻页']);
 断言.deepEqual(JSON.parse(JSON.stringify(事件序列[1])),{句柄:847362,操作:'翻页',参数:{}});
 console.log('宿主合同、失败显现、事件串行验证成功');
})().catch(失败原因=>{console.error(失败原因);process.exitCode=1});
