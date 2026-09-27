# -*- coding: utf-8 -*-
"""干净合成仓里 ㉗–㊱（外部支持库准入判据）的夹具（从 合成仓.py 拆出，控单件行数）。"""

from __future__ import annotations


def 准入夹具() -> dict:
    """返回 {相对路径: 内容}：准入 10 条在干净合成仓上必须全过。"""
    import json as _json

    def 转JSON文本(对象):
        return _json.dumps(对象, ensure_ascii=False, indent=2) + "\n"

    return {
        # ④ 广播段：判定.rs 调广播段并 continue；载入判定.json 写明广播段。
        "运行内核/装载入口/src/判定.rs": (
            "pub fn 判广播段() -> bool {\n"
            "    if 生命周期广播段(段.起, 段.止) {\n"
            "        continue;\n"
            "    }\n"
            "    true\n"
            "}\n"
            "fn 生命周期广播段(起: u32, 止: u32) -> bool {\n"
            "    起 >= 通知号段::生命周期起 && 止 <= 通知号段::生命周期止\n"
            "}\n"
        ),
        "扩展装载/载入约定/载入判定.json": 转JSON文本({
            "说明": "样例载入判定",
            "热载入与热卸载": "生命周期段按广播段判",
            "判定顺序的优先级": "号段冲突先于声明自洽",
        }),
        # ⑤ 通知口：四入口齐（适配器装载里的注册调用见上）。
        "跨语言适配/适配器实现/src/通知口.rs": (
            "pub struct 通知口;\n"
            "impl 通知口 {\n"
            "    pub fn 注册通知端点(&self, 标识串: *const u8, 函数: u32) { let _ = (标识串, 函数); }\n"
            "    pub fn 请求卸载(&self) {}\n"
            "    pub fn 延迟释放协商(&self) {}\n"
            "    pub fn 请求卸载按标识(&self) {}\n"
            "}\n"
        ),
        # ⑦ 接缝冻结：边界协议 + 扩展根声明 + 启动网关 dlsym。
        "跨语言适配/边界协议/边界协议.md": (
            "# 样例边界协议\n\n"
            "符号名 `GetPlatformInfo`（冻结；明示**不复刻**参照实现 `GetNewInf`）。\n"
        ),
        "扩展装载/扩展根声明.json": 转JSON文本({
            "说明": "样例扩展根声明",
            "扫描": {"找什么": "GetPlatformInfo"},
        }),
        "对外接口面/调用接口面/examples/启动网关.rs": (
            "//! 样例启动网关。\n"
            "use core::ffi::c_void;\n"
            'extern "C" { fn dlsym(句柄: *mut c_void, 名: *const u8) -> *mut c_void; }\n'
            "pub(crate) fn 取扩展声明(扩展目录: &str) -> Result<&'static 平台信息, String> {\n"
            "    let _ = 扩展目录;\n"
            "    Ok(unsafe { &*(core::ptr::null::<平台信息>()) })\n"
            "}\n"
            "pub fn 装(落点: &str) {\n"
            "    let mut 剔除的 = Vec::new();\n"
            "    match 取扩展声明(落点) {\n"
            "        Err(原因) => 剔除的.push((落点, 原因)),\n"
            "        Ok(_) => {}\n"
            "    }\n"
            '    for (落点, 原因) in &剔除的 { println!("  剔除 {落点}：{原因}"); }\n'
            "}\n"
            "pub fn 装配() {\n"
            '    let 符号 = unsafe { dlsym(core::ptr::null_mut(), c"GetPlatformInfo".as_ptr()) };\n'
            "    let _ = 符号;\n"
            "}\n"
            "pub fn 起服务() { 服务.跑服务(); }\n"
        ),
        # ⑧ 无死键：扩展包声明（无 提供宿主版本/提供内核版本）。
        "扩展根目录/原子支持库/样例支持库/包声明.json": 转JSON文本({
            "说明": "样例扩展声明",
            "名称": "样例支持库",
        }),
        # ⑨ crate-type：必备件规则 + 装配侧现场编（扩展 Cargo.toml 已在上方、无 [lib] crate-type）。
        "扩展装载/开发标准/必备件.json": 转JSON文本({
            "说明": "样例必备件",
            "扩展仓的 crate-type（只有一条路）": {
                "判据": "扩展仓的 [lib] 不许声明 crate-type；由装配侧 cargo rustc --crate-type cdylib 现场编",
            },
        }),
        "构建装配/上线切换/构建制品.py": (
            '"""样例装配器（带壳入口不算：无行首 __main__）。"""\n'
            "# 唯一那条路：cargo rustc --crate-type cdylib\n"
        ),
        # ⑩ 命令类别：一条合法类别（文件名 = 类别号）。
        "契约声明/命令类别/0000.json": 转JSON文本({
            "类别号": 0, "名称": "默认", "说明": "默认类别",
        }),
        # ⑭ 指纹可跑（静态：命令在 + 脚本在）。
        "扩展根目录/原子支持库/样例支持库/指纹.json": 转JSON文本({
            "说明": "样例指纹",
            "生成命令": "python3 扩展根目录/原子支持库/样例支持库/工具/重跑指纹.py --检查",
            "指纹": {},
        }),
        "扩展根目录/原子支持库/样例支持库/工具/重跑指纹.py": "import sys\nsys.exit(0)\n",
        # ⑯ 并发：线程安全断言 + 网关跑并发（启动网关走 服务.跑服务()，见上）。
        "跨语言适配/适配器实现/src/线程安全.rs": (
            "pub struct 适配器;\n"
            "unsafe impl Send for 适配器 {}\n"
            "unsafe impl Sync for 适配器 {}\n"
        ),
        "对外接口面/调用接口面/src/网关.rs": (
            "pub fn 跑并发() {\n"
            "    std::thread::scope(|域| { let _ = 域; });\n"
            "}\n"
        ),
    }
