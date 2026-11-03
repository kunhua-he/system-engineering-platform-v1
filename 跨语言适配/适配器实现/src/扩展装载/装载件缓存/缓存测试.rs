//! 装载件缓存 · 单测：解包链的正面与反面样本（指纹篡改 / 本体类型 / 重入 / 并发 / 落点不安全）。

use super::取件判据::{判定来源信任, 校验内容};
use super::缓存落盘::{写入缓存件, 创建缓存临时件, 缓存路径对象};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};
use v1_contract::容器;

use super::*;
use std::sync::{Arc, Barrier};

struct 测试目录 {
    目录根: PathBuf,
}
impl Drop for 测试目录 {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.目录根);
    }
}
fn 创建测试目录() -> 测试目录 {
    for 临时序号 in 0..128 {
        let 时间戳 = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let 目录根 = std::env::temp_dir().canonicalize().unwrap().join(format!(
            "装载件缓存验证-{}-{时间戳}-{临时序号}",
            std::process::id()
        ));
        match fs::create_dir(&目录根) {
            Ok(()) => return 测试目录 { 目录根 },
            Err(错误) if 错误.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(错误) => panic!("创建测试目录失败：{错误}"),
        }
    }
    panic!("测试目录竞争次数超限")
}
fn 写测试制品(目录根: &Path, 制品字节: &[u8]) -> PathBuf {
    let 制品文件 = 目录根.join("样例.支持库制品");
    fs::write(&制品文件, 制品字节).unwrap();
    制品文件
}
fn 缓存键路径(缓存目录: &Path, 代码字节: &[u8]) -> PathBuf {
    let 缓存键: String = 容器::算指纹(代码字节)
        .iter()
        .map(|字节| format!("{字节:02x}"))
        .collect();
    缓存目录.join(缓存键)
}

#[test]
fn 指纹篡改拒绝且不产生缓存() {
    let 测试目录 = 创建测试目录();
    let 缓存目录 = 测试目录.目录根.join("缓存");
    let mut 篡改制品 = 容器::装包(b"interface", b"native-code");
    let 本体段头 = 容器::文件头魔数.len() + 容器::段头长度 + b"interface".len();
    篡改制品[本体段头 + 容器::段头长度] ^= 1;
    assert_eq!(容器::校验段指纹(&篡改制品), Some(false));
    let 制品文件 = 写测试制品(&测试目录.目录根, &篡改制品);
    assert!(解包到缓存(&制品文件, &缓存目录).is_err());
    assert!(!缓存目录.exists());
    let mut 篡改制品 = 容器::装包(b"interface", b"native-code");
    篡改制品.pop();
    let 制品文件 = 写测试制品(&测试目录.目录根, &篡改制品);
    assert!(解包到缓存(&制品文件, &缓存目录).is_err());
    assert!(!缓存目录.exists());
}

#[test]
fn 本体类型及空码拒绝() {
    let 测试目录 = 创建测试目录();
    let 缓存目录 = 测试目录.目录根.join("缓存");
    let 技能制品 = 容器::装包三段(b"interface", b"skill", 容器::段类型_技能本体);
    let mut 伪装技能 = 技能制品.clone();
    let 本体段头 = 伪装技能.len() - 容器::指纹宽度 - 1;
    伪装技能[本体段头] = 容器::段类型_能力码;
    assert_eq!(容器::校验段指纹(&伪装技能), Some(false));
    let 空码制品 = 容器::装包(b"interface", b"");
    for 制品字节 in [技能制品, 伪装技能, 空码制品] {
        let 制品文件 = 写测试制品(&测试目录.目录根, &制品字节);
        assert!(解包到缓存(&制品文件, &缓存目录).is_err());
        assert!(!缓存目录.exists());
    }
}

#[test]
fn 完整落盘重入及内容定键() {
    let 测试目录 = 创建测试目录();
    let 缓存目录 = 测试目录.目录根.join("缓存");
    let 代码字节 = b"native-code";
    let 目标路径 = 缓存键路径(&缓存目录, 代码字节);
    for 制品字节 in [
        容器::装包(b"interface", 代码字节),
        容器::装包(b"changed", 代码字节),
    ] {
        let 制品文件 = 写测试制品(&测试目录.目录根, &制品字节);
        assert_eq!(解包到缓存(&制品文件, &缓存目录).unwrap(), 目标路径);
        assert_eq!(解包到缓存(&制品文件, &缓存目录).unwrap(), 目标路径);
        assert_eq!(fs::read(&目标路径).unwrap(), 代码字节);
    }
    assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 1);
}

#[test]
fn 同键并发只见完整制品() {
    let 测试目录 = 创建测试目录();
    let 缓存目录 = 测试目录.目录根.join("缓存");
    let 代码字节 = vec![0x42; 256 * 1024];
    let 制品文件 = 写测试制品(&测试目录.目录根, &容器::装包(b"interface", &代码字节));
    let 目标路径 = 缓存键路径(&缓存目录, &代码字节);
    let 并发屏障 = Arc::new(Barrier::new(9));
    let mut 线程列表 = Vec::new();
    for _ in 0..8 {
        let 线程制品 = 制品文件.clone();
        let 线程缓存 = 缓存目录.clone();
        let 线程屏障 = 并发屏障.clone();
        线程列表.push(std::thread::spawn(move || {
            线程屏障.wait();
            解包到缓存(&线程制品, &线程缓存).unwrap()
        }));
    }
    并发屏障.wait();
    while 线程列表.iter().any(|工作线程| !工作线程.is_finished()) {
        match fs::read(&目标路径) {
            Ok(缓存字节) => assert_eq!(缓存字节, 代码字节),
            Err(错误) => assert_eq!(错误.kind(), std::io::ErrorKind::NotFound),
        }
        std::thread::yield_now();
    }
    for 工作线程 in 线程列表 {
        assert_eq!(工作线程.join().unwrap(), 目标路径);
    }
    assert_eq!(fs::read(&目标路径).unwrap(), 代码字节);
    assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 1);
}

/// **目标位置是非普通文件 ⇒ 仍拒**：这不是脏件（内容坏了），是落点不安全 —— 删了也照样不能落。
/// 「长度 / 内容不符的脏件当未命中重写」连同其余四组反证在 `装载件缓存/预算判据.rs::预算测试`。
#[test]
fn 目标位置是非普通文件即拒() {
    let 测试目录 = 创建测试目录();
    let 缓存目录 = 测试目录.目录根.join("缓存");
    fs::create_dir(&缓存目录).unwrap();
    let 制品文件 = 写测试制品(&测试目录.目录根, &容器::装包(b"interface", b"native-code"));
    let 目标路径 = 缓存键路径(&缓存目录, b"native-code");
    fs::create_dir(&目标路径).unwrap();
    assert!(
        解包到缓存(&制品文件, &缓存目录).is_err(),
        "目录当缓存件必须拒"
    );
    assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 1);
}

#[cfg(unix)]
#[test]
fn 符号链接目标及目录拒绝() {
    use std::os::unix::fs::symlink;
    let 测试目录 = 创建测试目录();
    let 缓存目录 = 测试目录.目录根.join("缓存");
    fs::create_dir(&缓存目录).unwrap();
    let 制品文件 = 写测试制品(&测试目录.目录根, &容器::装包(b"interface", b"native-code"));
    let 目标路径 = 缓存键路径(&缓存目录, b"native-code");
    symlink(&制品文件, &目标路径).unwrap();
    assert!(解包到缓存(&制品文件, &缓存目录).is_err());
    fs::remove_file(&目标路径).unwrap();
    symlink(测试目录.目录根.join("不存在"), &目标路径).unwrap();
    assert!(解包到缓存(&制品文件, &缓存目录).is_err());
    fs::remove_file(&目标路径).unwrap();
    fs::remove_dir(&缓存目录).unwrap();
    symlink(&测试目录.目录根, &缓存目录).unwrap();
    assert!(解包到缓存(&制品文件, &缓存目录).is_err());
    assert!(!缓存键路径(&测试目录.目录根, b"native-code").exists());
}

#[test]
fn 中断残件忽略且失败临时件清理() {
    let 测试目录 = 创建测试目录();
    let 缓存目录 = 测试目录.目录根.join("缓存");
    fs::create_dir(&缓存目录).unwrap();
    let 残件路径 = 缓存目录.join(".中断.临时");
    fs::write(&残件路径, b"partial").unwrap();
    let 制品文件 = 写测试制品(&测试目录.目录根, &容器::装包(b"interface", b"native-code"));
    let 目标路径 = 解包到缓存(&制品文件, &缓存目录).unwrap();
    assert_eq!(fs::read(&目标路径).unwrap(), b"native-code");
    assert_eq!(fs::read(&残件路径).unwrap(), b"partial");
    let (临时清理, mut 临时文件) = 创建缓存临时件(&缓存目录, "失败样例").unwrap();
    let 清理路径 = 临时清理.临时路径.clone();
    let 失败结果: std::io::Result<()> = (|| {
        let 临时清理 = 临时清理;
        临时文件.write_all(b"partial")?;
        drop(临时文件);
        fs::hard_link(&临时清理.临时路径, &缓存目录)
    })();
    assert!(失败结果.is_err());
    assert!(!清理路径.exists());
    assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 2);
}

/// **平台身份（段 `20`）不符即拒、且一个缓存件都不落** —— 这一条要的是**反向样本**。
///
/// 正向例子只能证明「身份相符时跑得通」，证不了「不符时真会挡」；
/// 平台身份是「这台机器 + 这个 rustc」的产物，判错就是**静默降级**（裁决 §三 明禁）。
#[test]
fn 平台身份不符即拒且不产缓存() {
    let 测试目录 = 创建测试目录();
    let 缓存目录 = 测试目录.目录根.join("缓存");
    let 制品身份 = "x86_64-unknown-linux-gnu";
    let 载荷 = 容器::打包执行体载荷(制品身份, b"native-code");
    let 执行体包件 = 容器::装包三段(b"interface", &载荷, 容器::段类型_本机执行体);
    let 制品文件 = 写测试制品(&测试目录.目录根, &执行体包件);

    // ① 制品给别的平台、本机是另一个 ⇒ 拒，且拒在缓存键之前 ⇒ 一个缓存件都不落。
    let 拒绝结果 = 解包模块执行体到缓存(&制品文件, &缓存目录, "aarch64-apple-darwin");
    assert!(
        拒绝结果.is_err(),
        "平台身份不符必须拒，实际放过了：{拒绝结果:?}"
    );
    assert!(
        拒绝结果.unwrap_err().contains(制品身份),
        "拒的理由要带上制品自称的那个身份，才定位得到是哪个制品给错了平台"
    );
    assert!(
        !缓存目录.exists() || fs::read_dir(&缓存目录).unwrap().count() == 0,
        "拒之后不许留下任何缓存件"
    );

    // ② 报上制品那个身份 ⇒ 过，且落盘的是**纯执行体**（身份是执行体的属性，落盘前剥掉）。
    let 落点 = 解包模块执行体到缓存(&制品文件, &缓存目录, 制品身份).expect("身份相符必须过");
    assert_eq!(
        fs::read(&落点).unwrap(),
        b"native-code",
        "落盘的是执行体字节，不带身份前缀"
    );
}

/// 四件事各判各的、互不顶替 —— 每一面各造一个**只有它该拒**的现场：
/// ① 内容坏而来源好；② 来源是符号链接而内容好；③ 来源与内容都好而落点链含符号链接；
/// ④ 写入只认「字节 + 落点」这一对（同内容同落点、异内容异名）。
#[test]
fn 四者各判各的不互相顶替() {
    use std::os::unix::fs::symlink;
    let 测试目录 = 创建测试目录();
    let 缓存目录 = 测试目录.目录根.join("缓存");
    fs::create_dir(&缓存目录).unwrap();
    let 好制品 = 容器::装包(b"interface", b"native-code");

    // ① 内容校验拒 · 来源信任放行 ⇒ 一个缓存件都不该落下。
    let mut 坏字节 = 好制品.clone();
    坏字节.pop();
    assert!(校验内容(&坏字节).is_err());
    let 坏制品文件 = 写测试制品(&测试目录.目录根, &坏字节);
    assert!(判定来源信任(&坏制品文件).is_ok());
    assert!(解包到缓存(&坏制品文件, &缓存目录).is_err());
    assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 0);

    // ② 来源信任拒 · 内容校验放行 ⇒ 链接指到的是真制品，照样不落。
    let 好制品文件 = 写测试制品(&测试目录.目录根, &好制品);
    assert!(校验内容(&fs::read(&好制品文件).unwrap()).is_ok());
    let 链接制品 = 测试目录.目录根.join("链接制品.支持库制品");
    symlink(&好制品文件, &链接制品).unwrap();
    assert!(判定来源信任(&链接制品).is_err());
    assert!(解包到缓存(&链接制品, &缓存目录).is_err());
    assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 0);

    // ③ 路径对象拒 · 来源与内容都放行 ⇒ 拒的是落点链，不是制品。
    let 链接缓存 = 测试目录.目录根.join("链接缓存");
    symlink(&缓存目录, &链接缓存).unwrap();
    assert!(缓存路径对象(&链接缓存).is_err());
    assert!(判定来源信任(&好制品文件).is_ok());
    assert!(解包到缓存(&好制品文件, &链接缓存).is_err());

    // ④ 写入只认「字节 + 落点」：名由内容定 ⇒ 同内容重入落同一件、异内容异名。
    let 首次落点 = 写入缓存件(&缓存目录, &由内容算(b"native-code"), b"native-code").unwrap();
    assert_eq!(fs::read(&首次落点).unwrap(), b"native-code");
    let 重算落点 = 写入缓存件(&缓存目录, &由内容算(b"native-code"), b"native-code").unwrap();
    assert_eq!(重算落点, 首次落点);
    let 异内容落点 = 缓存目录.join(由内容算(b"other-code"));
    assert_ne!(异内容落点, 首次落点);
    assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 1);
}
