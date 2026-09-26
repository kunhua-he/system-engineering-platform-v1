//! 对外边界的测试（一）**读侧**：导出符号恰好三个 · `平台_取接口描述`。
//!
//! **整文件即测试**（`lib.rs` 用 `#[cfg(test)] #[path]` 挂进来）。拆成三份的理由：
//! 单个源文件 ≤ 400 行（`开发规范.md` 第六节）。同族两份见 `调用测试.rs` · `写出测试.rs`。
//!
//! # 每条判据都带反向样本（`项目文档/设计文档/判据的可信性.md` 第五节）
//!
//! | 判据 | 反向样本（注入一个该抓的违规 ⇒ 必须报红） |
//! |---|---|
//! | 导出符号恰好三个 · 不含接缝 | 扫一段带多余 `平台_*` 导出 / 带 `GetPlatformInfo` 的源码 |
//! | 长度出参正确 | 少报 1 字节 ⇒ 逐字节比对必挂 |
//! | 内容与 `能力清单()` 一致 | 编一个不存在的能力名 ⇒ 必找不到 |
//!
//! **空集不算通过**：每条断言都先钉住「样本非空」（`长 > 0` / `!清单.is_empty()`）。

use super::*;

// ════════════════════════════════════════════════════════════════════════════
// 判据：导出符号恰好一组三个 · 不含接缝
// ════════════════════════════════════════════════════════════════════════════

/// 从源码文本里抽**导出属性**里的符号名。
///
/// 口径与一键验证一致：只认 `#[unsafe(export_name = "…")]` / `#[export_name = "…")]`
/// 这种**属性**形（光写 `extern "C"` 会被 mangled、不算导出），并先**去行注释**
/// （注释里提一句 `export_name = "…"` 不算导出）。
fn 扫导出名(文本: &str) -> Vec<String> {
    let 净 = 去行注释(文本);
    let 形 = ["#[unsafe(export_name = \"", "#[export_name = \""];
    let mut 出 = Vec::new();
    let mut 余 = 净.as_str();
    loop {
        let mut 最优位 = usize::MAX;
        let mut 最优前 = "";
        for 前 in 形 {
            if let Some(位) = 余.find(前) && 位 < 最优位 {
                最优位 = 位;
                最优前 = 前;
            }
        }
        if 最优位 == usize::MAX {
            break;
        }
        let 尾 = &余[最优位 + 最优前.len()..];
        let Some(闭) = 尾.find('"') else { break };
        出.push(尾[..闭].to_owned());
        余 = &尾[闭 + 1..];
    }
    出
}

/// 去行注释（长度无关；本文件只拿它避免「注释里的 `export_name`」被当导出）。
fn 去行注释(文本: &str) -> String {
    let mut 出 = String::with_capacity(文本.len());
    for 行 in 文本.lines() {
        match 行.find("//") {
            Some(位) => 出.push_str(&行[..位]),
            None => 出.push_str(行),
        }
        出.push('\n');
    }
    出
}

/// 本 crate 的**生产源**（`include_str!` 读的是真源码，不是另存的一份）。
const 生产源: [(&str, &str); 5] = [
    ("lib.rs", include_str!("lib.rs")),
    ("契约读取.rs", include_str!("契约读取.rs")),
    ("小写出.rs", include_str!("小写出.rs")),
    ("接口描述.rs", include_str!("接口描述.rs")),
    ("边界面.rs", include_str!("边界面.rs")),
];

/// 判据：本 crate 生产代码里导出符号**恰好一组三个**，且**不含**接缝 `GetPlatformInfo`。
#[test]
fn 导出符号_恰好三个且不含接缝() {
    let 允许: Vec<String> = ["平台_取接口描述", "平台_调用", "平台_释放值"]
        .iter()
        .map(|名| (*名).to_owned())
        .collect();

    let mut 名 = Vec::new();
    for (_, 文) in 生产源 {
        名.extend(扫导出名(文));
    }
    assert_eq!(名.len(), 3, "三个符号各恰好一次（重复导出同一名也是多条腿）：{名:?}");

    let mut 去重 = 名.clone();
    去重.sort();
    去重.dedup();
    assert_eq!(去重, 允许, "导出符号恰好这三个，一个不多一个不少");

    assert!(
        !名.iter().any(|一| 一 == "GetPlatformInfo"),
        "接缝是**反方向**（扩展 → 宿主），本边界不许导出它"
    );
    for (文件, 文) in 生产源 {
        assert!(
            !文.contains("#[no_mangle]"),
            "{文件} 不许用 `#[no_mangle]`（导出只走 `export_name` 这一条路）"
        );
    }

    // ── 反向样本：判据不是空转 ──
    let 注入多余 = r#"#[unsafe(export_name = "平台_多一个")]
pub extern "C" fn 多余() -> usize { 0 }"#;
    let 抓到 = 扫导出名(注入多余);
    assert_eq!(抓到, vec!["平台_多一个".to_owned()], "反向样本：多余的导出必须被扫出来");
    assert!(!允许.contains(&抓到[0]), "它不在允许集里 ⇒ 判据会报红（这正是它该抓的违规）");

    let 注入接缝 = r#"#[unsafe(export_name = "GetPlatformInfo")]
pub extern "C" fn 取() {}"#;
    assert!(
        扫导出名(注入接缝).iter().any(|一| 一 == "GetPlatformInfo"),
        "反向样本：接缝符号也必须被扫出来（否则「不含 GetPlatformInfo」是空话）"
    );

    // 注释里提一句不算导出（去行注释真的生效）。
    assert!(扫导出名("// #[unsafe(export_name = \"平台_注释里\")]\n").is_empty());
}

// ════════════════════════════════════════════════════════════════════════════
// 判据：平台_取接口描述
// ════════════════════════════════════════════════════════════════════════════

/// 判据：长度出参**正确**（等于 JSON 的字节数），且与 Rust 级读数逐字节相同。
#[test]
fn 取接口描述_长度出参等于字节数() {
    let mut 长: u32 = 0;
    // SAFETY: 长 是本函数里的可写 u32（`平台_取接口描述` 的 Safety 契约）。
    let 首 = unsafe { 平台_取接口描述(&mut 长) };
    assert!(!首.is_null(), "有接口可描述 ⇒ 不许给空指针");
    assert!(长 > 0, "空集不算通过：描述必须非空");

    // 逐字节读到 NUL：长度出参必须真是这段字节的长度，不是别的数。
    let mut 数 = 0usize;
    loop {
        // SAFETY: 首 指向终生有效的缓冲（`边界面.rs` 文件头「所有权」），按协议 NUL 结尾。
        let 字 = unsafe { *首.add(数) };
        if 字 == 0 {
            break;
        }
        数 += 1;
    }
    assert_eq!(数, 长 as usize, "长度出参必须等于 JSON 的字节数");

    // 与 Rust 级同源读数比对（导出符号交出的就是它泄漏出来的那一份）。
    let 边界 = 对外边界::新建(&[v1_loader::底座声明()]).expect("底座自己的声明必须载得进来");
    let 期望 = 边界.取接口描述();
    assert_eq!(长 as usize, 期望.len(), "长度出参与 Rust 级读数必须同数");
    // SAFETY: 同上（首 指向 长 字节可读的缓冲）。
    let 字节 = unsafe { core::slice::from_raw_parts(首 as *const u8, 长 as usize) };
    assert_eq!(字节, 期望.as_bytes(), "导出符号交出的字节必须与 Rust 级读数逐字节相同");

    // ── 反向样本：判据对长度敏感 —— 少报 1 字节，比对必挂 ──
    assert_ne!(
        &字节[..字节.len() - 1],
        期望.as_bytes(),
        "反向样本：少一字节就不相等 ⇒ 「长度正确」这条判据不是空转"
    );
}

/// 判据：`长度` 传空指针**不崩**。
#[test]
fn 取接口描述_长度指针为空不崩() {
    // SAFETY: 传空指针；本函数按 Safety 契约当场返回空指针，不写任何内存。
    let 出 = unsafe { 平台_取接口描述(core::ptr::null_mut()) };
    assert!(出.is_null(), "无法报告长度 ⇒ 不交出一个不可读的缓冲（约定：给空指针）");
}

/// 判据：JSON 的内容与 `能力清单()` **一致**（逐条对编号 / 名称 / 参数个数 / 返回类型）。
#[test]
fn 取接口描述_内容与能力清单一致() {
    let 边界 = 对外边界::新建(&[v1_loader::底座声明()]).expect("底座");
    let json = 边界.取接口描述();
    let 清单 = 边界.能力清单();
    assert!(!清单.is_empty(), "空集不算通过：底座声明至少有 1 条命令");

    for 摘要 in &清单 {
        for 片段 in [
            format!("\"编号\": {}", 摘要.编号),
            format!("\"名称\": \"{}\"", 摘要.名称),
            format!("\"参数个数\": {}", 摘要.参数个数),
            format!("\"返回类型\": {}", 摘要.返回类型),
        ] {
            assert!(json.contains(&片段), "接口描述里必须有 {片段}");
        }
    }
    // 参数表行序与可抛错误码也要在（「某条能力怎么调」）。
    assert!(json.contains("\"参数表\": ["), "参数表必须在");
    assert!(json.contains("\"可抛错误码\": ["), "可抛错误码必须在");
    assert!(json.contains("\"可自愈\": true"), "三项业务判断必须到得了运行期");

    // ── 反向样本：判据对内容敏感 —— 编一个不存在的能力名，必找不到 ──
    assert!(!json.contains("\"名称\": \"没有这个能力\""));
}

