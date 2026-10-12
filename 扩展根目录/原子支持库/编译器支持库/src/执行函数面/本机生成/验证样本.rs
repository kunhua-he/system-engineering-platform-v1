use super::{生成本机源码, 本机依赖, 本机生成请求, 本机源码产物, 本机生成错误};
use crate::语义::名号表;
use std::{fs, path::PathBuf, process::Command};

const 常量初版: &[u8] = include_bytes!("样本/常量初版.程序文本");
const 常量改版: &[u8] = include_bytes!("样本/常量改版.程序文本");
const 支持库组合: &[u8] = include_bytes!("样本/支持库组合.程序文本");

fn 生成样本(
    程序文本: &[u8], 命令表: &名号表, 锁定依赖: &[本机依赖],
    工具链身份: &str, 平台身份: &str,
) -> Result<本机源码产物, 本机生成错误> {
    生成本机源码(&本机生成请求 {
        程序文本, 命令表, 常量表: &名号表::空实例(),
        类型表: &名号表::从项(vec![("整数型".as_bytes().to_vec(), 1), ("文本型".as_bytes().to_vec(), 4)]),
        锁定依赖, 工具链身份, 平台身份,
    })
}

fn 生成纯样本(程序文本: &[u8]) -> Result<本机源码产物, 本机生成错误> {
    生成样本(程序文本, &名号表::空实例(), &[], "纯函数测试工具链", "纯函数测试平台")
}

struct 验证目录守卫(PathBuf);

impl Drop for 验证目录守卫 {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}

fn 取测试工具链() -> (String, String, PathBuf) {
    let 工具链命令 = PathBuf::from(std::env::var_os("RUSTC").unwrap_or_else(|| "rustc".into()));
    let 工具链输出 = Command::new(&工具链命令).arg("-vV").output().unwrap();
    assert!(工具链输出.status.success());
    let 工具链身份 = String::from_utf8(工具链输出.stdout).unwrap();
    let 平台身份 = 工具链身份.lines().find_map(|记录行| 记录行.strip_prefix("host: ")).unwrap().to_owned();
    (工具链身份, 平台身份, 工具链命令)
}

fn 构建并执行(产物: &本机源码产物, 工具链命令: &PathBuf, 运行参数: &[&str]) -> String {
    let 时间戳 = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos();
    let 验证目录 = 验证目录守卫(std::env::temp_dir().join(format!("v1-native-gen-{}-{时间戳}", std::process::id())));
    fs::create_dir(&验证目录.0).unwrap();
    let 源码路径 = 验证目录.0.join("native_probe.rs");
    let 执行路径 = 验证目录.0.join("native_probe");
    let 依赖目录 = std::env::current_exe().unwrap().parent().unwrap().to_owned();
    let 契约产物表: Vec<_> = fs::read_dir(&依赖目录).unwrap().map(|目录项| 目录项.unwrap().path()).filter(|路径|
        路径.file_name().unwrap().to_string_lossy().starts_with("libv1_contract-")
            && 路径.extension().is_some_and(|后缀| 后缀 == "rlib")
    ).collect();
    assert_eq!(契约产物表.len(), 1, "请用本腿独立target目录验证，避免混用工具链契约产物");
    let 验证入口 = r#"
fn main() {
    let 运行参数: Vec<String> = std::env::args().skip(1).collect();
    let mut 调用次数 = 0usize;
    let mut 宿主调用 = |能力号: u32, 入参: &[数据槽], 返回槽: &mut 数据槽| {
        调用次数 += 1;
        let 预期能力号: u32 = 运行参数[0].parse().unwrap();
        assert_eq!(能力号, 预期能力号);
        assert_eq!(入参.len(), 1);
        assert_eq!(入参[0].类型标签, 1);
        assert_eq!(入参[0].槽标志位, 0);
        assert_eq!(入参[0].槽字节长度, 8);
        let 返回整数: i64 = 运行参数[1].parse().unwrap();
        if 运行参数.get(2).is_some_and(|参数| 参数 == "类型不符") {
            *返回槽 = 数据槽::内联槽(4u32.into(), 返回整数 as u64, 8);
        } else {
            *返回槽 = 数据槽::内联槽(1u32.into(), 返回整数 as u64, 8);
        }
        Ok(())
    };
    match 模块执行(&mut 宿主调用, &[]) {
        Ok(返回整数) => println!("{}", 返回整数),
        Err(执行错误) => println!("错误:{:?}", 执行错误),
    }
    if !运行参数.is_empty() { assert_eq!(调用次数, 1); }
}
"#;
    fs::write(&源码路径, format!("{}\n{验证入口}", 产物.执行源码)).unwrap();
    let 编译输出 = Command::new(工具链命令).arg("--edition=2024")
        .arg("--crate-name").arg("native_probe").arg("--target").arg(&产物.平台身份)
        .arg("--extern").arg(format!("v1_contract={}", 契约产物表[0].display()))
        .arg("-L").arg(format!("dependency={}", 依赖目录.display()))
        .arg(&源码路径).arg("-o").arg(&执行路径).output().unwrap();
    assert!(编译输出.status.success(), "{}", String::from_utf8_lossy(&编译输出.stderr));
    let 执行输出 = Command::new(&执行路径).args(运行参数).output().unwrap();
    assert!(执行输出.status.success(), "{}", String::from_utf8_lossy(&执行输出.stderr));
    String::from_utf8(执行输出.stdout).unwrap().trim().to_owned()
}

#[test]
fn 来源证据与生成结果确定性关联() {
    let 初版产物 = 生成纯样本(常量初版).unwrap();
    assert_eq!(初版产物, 生成纯样本(常量初版).unwrap());
    assert_eq!(初版产物.原文证据, 常量初版);
    assert_eq!(初版产物.工具链身份, "纯函数测试工具链");
    assert_ne!(初版产物.执行源码, 生成纯样本(常量改版).unwrap().执行源码);
    assert_eq!(初版产物.命令表证据, 名号表::空实例().编码());
    assert!(初版产物.锁定依赖.is_empty());
    assert!(!初版产物.执行源码.contains("42i64"));
}

#[test]
fn 常量源码决定真实返回() {
    let (工具链身份, 平台身份, 工具链命令) = 取测试工具链();
    let 初版产物 = 生成样本(常量初版, &名号表::空实例(), &[], &工具链身份, &平台身份).unwrap();
    let 改版产物 = 生成样本(常量改版, &名号表::空实例(), &[], &工具链身份, &平台身份).unwrap();
    let 初版返回 = 构建并执行(&初版产物, &工具链命令, &[]);
    let 改版返回 = 构建并执行(&改版产物, &工具链命令, &[]);
    assert_eq!(初版返回, "42");
    assert_eq!(改版返回, "43");
    println!("本机真实执行：40＋2={初版返回}；40＋3={改版返回}；平台={平台身份}；{}", 工具链身份.lines().next().unwrap());
}

#[test]
fn 既有左结合与括号决定真实算术() {
    let (工具链身份, 平台身份, 工具链命令) = 取测试工具链();
    for (表达式原文, 预期返回) in [("2 ＋ 3 × 4", "20"), ("2 ＋ (3 × 4)", "14"), ("-5 ＋ 2", "-3"), ("9 ÷ 2", "4")] {
        let 程序文本 = format!(".版本 2\n.子程序 计算结果, 整数型\n返回 ({表达式原文})\n");
        let 产物 = 生成样本(程序文本.as_bytes(), &名号表::空实例(), &[], &工具链身份, &平台身份).unwrap();
        assert_eq!(构建并执行(&产物, &工具链命令, &[]), 预期返回);
    }
}

#[test]
fn 算术溢出与除零不产生伪成功() {
    let (工具链身份, 平台身份, 工具链命令) = 取测试工具链();
    for 表达式原文 in ["9223372036854775807 ＋ 1", "5 ÷ 0", "-9223372036854775808 ÷ -1"] {
        let 程序文本 = format!(".版本 2\n.子程序 计算结果, 整数型\n返回 ({表达式原文})\n");
        let 产物 = 生成样本(程序文本.as_bytes(), &名号表::空实例(), &[], &工具链身份, &平台身份).unwrap();
        assert_eq!(构建并执行(&产物, &工具链命令, &[]), "错误:算术失败");
    }
}

#[test]
fn 非法文本语义类型与未支持节点生成前拒绝() {
    for 程序文本 in [
        ".版本 3\n.子程序 计算结果, 整数型\n返回 (1)\n",
        ".版本 2\n.子程序 计算结果, 文本型\n返回 (1)\n",
        ".版本 2\n.子程序 计算结果, 未知类型\n返回 (1)\n",
        ".版本 2\n.子程序 计算结果, 整数型\n返回 (未知变量)\n",
        ".版本 2\n.子程序 计算结果, 整数型\n返回 (“未结束)\n",
        ".版本 2\n.子程序 计算结果, 整数型\n返回 (9223372036854775808)\n",
        ".版本 2\n.子程序 计算结果, 整数型\n返回 (1)\n返回 (2)\n",
        ".版本 2\n.子程序 计算结果, 整数型\n.局部变量 中间结果, 整数型\n返回 (1)\n",
        ".版本 2\n.子程序 计算结果, 整数型\n返回 (“文本”)\n",
    ] {
        assert!(生成纯样本(程序文本.as_bytes()).is_err(), "错误程序被接受：{程序文本}");
    }
    assert!(matches!(生成纯样本(&[0xff]), Err(本机生成错误::来源缺失)));
    assert!(matches!(生成纯样本(支持库组合), Err(本机生成错误::语言语义(_))));
}

#[test]
fn 表达式残留记号拒绝() {
    for 表达式原文 in ["1 ＋", "1 2", "1()", "(1))", "((1)", "1,,", "1 ＞ 0"] {
        let 程序文本 = format!(".版本 2\n.子程序 计算结果, 整数型\n返回 ({表达式原文})\n");
        assert!(生成纯样本(程序文本.as_bytes()).is_err(), "残留记号被忽略：{表达式原文}");
    }
}

#[test]
fn 锁定依赖缺失拒绝() {
    let 命令表 = 名号表::从项(vec![("支持库整数".as_bytes().to_vec(), 1101)]);
    assert!(matches!(生成样本(支持库组合, &命令表, &[], "测试工具链", "测试平台"), Err(本机生成错误::依赖不匹配)));
}

#[test]
fn 未知号与错签名依赖生成前拒绝() {
    let 命令表 = 名号表::从项(vec![("支持库整数".as_bytes().to_vec(), 1101)]);
    let 缺失依赖 = 本机依赖 {
        名称: "不存在的能力".as_bytes().to_vec(), 能力号: u16::MAX,
        入参类型表: vec![1], 返回类型: 1,
    };
    let 错型依赖 = 本机依赖 {
        名称: "支持库整数".as_bytes().to_vec(), 能力号: 1101,
        入参类型表: vec![4], 返回类型: 1,
    };
    let 错号依赖 = 本机依赖 { 能力号: 1103, ..错型依赖.clone() };
    let 错返回依赖 = 本机依赖 { 返回类型: 4, ..错型依赖.clone() };
    for 依赖签名 in [缺失依赖, 错型依赖, 错号依赖, 错返回依赖] {
        assert!(matches!(生成样本(支持库组合, &命令表, &[依赖签名], "测试工具链", "测试平台"),
            Err(本机生成错误::依赖不匹配)));
    }
}

#[test]
fn 缺失来源与超限原文生成前拒绝() {
    for (工具链身份, 平台身份) in [("", "测试平台"), ("测试工具链", " ")] {
        assert!(matches!(生成样本(常量初版, &名号表::空实例(), &[], 工具链身份, 平台身份),
            Err(本机生成错误::来源缺失)));
    }
    assert!(matches!(生成纯样本(&vec![b' '; 64 * 1024 + 1]), Err(本机生成错误::来源缺失)));
}
