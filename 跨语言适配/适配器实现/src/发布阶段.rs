//! 发布阶段目录 —— 候选发布四阶段（创作 · 待验 · 发布 · 旧版本）的**目录分层**。
//!
//! # 为什么四类要分开
//!
//! 一份制品在发布链上经过四个互不相同的处置面：**创作**（刚成形、尚未校验）·
//! **待验**（已校验、尚未上流量）· **发布**（正在服务的那一份）· **旧版本**（被新版顶下来的那几份）。
//! 四者混在一个目录里 ⇒ 「哪一份在服务」只能靠内存态推断，进程一退就丢；分开 ⇒ 归属在盘上可判。
//!
//! # 与内存态候选的关系
//!
//! `候选发布.rs` 的副本 / 快照只解决「候选不污染主实例」这一半（进程内）；
//! 本件补另一半：**四类目录**。两者不互相替代 —— 内存态管在途引用，目录管跨重启的归属。
//!
//! # 落点
//!
//! 一律 `<运行数据根>/缓存/<发布根子目录名>/<阶段名>`（判据 ⑳/㉕：不落源码树 · 不自拼路径）。
//! [`默认发布根目录`] 解析不出根 ⇒ `None`（**不退回源码树、不退回 `/tmp`**），
//! 调用方据此报结构化失败。

use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use v1_dataroot::{子目录, 子目录路径, 解析当前环境};

/// 发布根在缓存类下的子目录名（目录名是事实，不是文案）。
const 发布根子目录名: &str = "候选发布";

/// 中断写入留下的临时件后缀（停机恢复只识别、不自动重放）。
const 临时件后缀: &str = ".临时";

/// 四类发布阶段。**封闭枚举** —— 判别值固定，与 [`发布阶段::全集`] 的次序一致。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum 发布阶段 {
    /// 创作：制品刚成形、尚未校验。
    创作 = 0,
    /// 待验：已校验、尚未上流量。
    待验 = 1,
    /// 发布：正在服务的那一份。
    发布 = 2,
    /// 旧版本：被新版顶下来的那几份（仍被在途引用的要留）。
    旧版本 = 3,
}

impl 发布阶段 {
    /// 本阶段在磁盘上的目录名。**全平台统一**（不随界面语言变 —— 目录名是事实，不是文案）。
    pub const fn 取名称(self) -> &'static str {
        match self {
            Self::创作 => "创作",
            Self::待验 => "待验",
            Self::发布 => "发布",
            Self::旧版本 => "旧版本",
        }
    }

    /// 四类全表。次序与判别值一致（`0..=3`）。
    pub const 全集: [Self; 4] = [Self::创作, Self::待验, Self::发布, Self::旧版本];
}

/// 某一阶段的目录路径。**只拼路径，不建目录**（建目录是 [`确保阶段目录`] 的事 ——
/// 「只是想算个路径」不该有副作用）。
pub fn 阶段目录路径(发布根: &Path, 阶段: 发布阶段) -> PathBuf {
    发布根.join(阶段.取名称())
}

/// 建出某一阶段目录并交出路径（父目录一并建）。
pub fn 确保阶段目录(发布根: &Path, 阶段: 发布阶段) -> std::io::Result<PathBuf> {
    let 路径 = 阶段目录路径(发布根, 阶段);
    fs::create_dir_all(&路径)?;
    Ok(路径)
}

/// 默认发布根 = `<运行数据根>/缓存/<发布根子目录名>`。
///
/// 解析不出根 ⇒ `None`（**不退回源码树、不退回 `/tmp`**）。
pub fn 默认发布根目录() -> Option<PathBuf> {
    let 根目录 = 解析当前环境().ok()?;
    Some(子目录路径(&根目录, 子目录::缓存).join(发布根子目录名))
}

/// 落一份制品进**创作**目录（原子发布 · 同键重入交回同一路径）。
///
/// 失败一律给一句可读原因，不 panic、不静默落进源码树。
pub fn 落创作件(发布根: &Path, 键名: &str, 字节: &[u8]) -> Result<PathBuf, String> {
    let 创作目录 = 确保阶段目录(发布根, 发布阶段::创作)
        .map_err(|错误| format!("建不出创作目录：{错误}"))?;
    原子落件(&创作目录, 键名, 字节)
}

/// 落一份制品进**待验**目录（原子发布 · 同键重入交回同一路径）。
pub fn 落待验件(发布根: &Path, 键名: &str, 字节: &[u8]) -> Result<PathBuf, String> {
    let 待验目录 = 确保阶段目录(发布根, 发布阶段::待验)
        .map_err(|错误| format!("建不出待验目录：{错误}"))?;
    原子落件(&待验目录, 键名, 字节)
}

/// **晋级到发布**：同名旧发布件先归档进**旧版本**目录，再把待验件挪进**发布**目录。
///
/// 归档而不是删除 —— 仍被在途引用持有的那一份不许被抹掉（`候选发布.rs` 的租约语义在盘上的对应）。
pub fn 晋级到发布(发布根: &Path, 键名: &str) -> Result<PathBuf, String> {
    let 待验目录 = 阶段目录路径(发布根, 发布阶段::待验);
    let 发布目录 = 确保阶段目录(发布根, 发布阶段::发布)
        .map_err(|错误| format!("建不出发布目录：{错误}"))?;
    let 待验件 = 待验目录.join(键名);
    if !待验件.is_file() {
        return Err("待验目录里没有这一份，不晋级".to_owned());
    }
    let 发布件 = 发布目录.join(键名);
    if 发布件.exists() {
        let 旧版本目录 = 确保阶段目录(发布根, 发布阶段::旧版本)
            .map_err(|错误| format!("建不出旧版本目录：{错误}"))?;
        let 归档路径 = 旧版本目录.join(归档名(键名));
        fs::rename(&发布件, &归档路径)
            .map_err(|错误| format!("旧版本归档失败：{错误}"))?;
    }
    fs::rename(&待验件, &发布件).map_err(|错误| format!("晋级失败：{错误}"))?;
    Ok(发布件)
}

/// 归档名 = `<键名>.<纳秒>`：同一键名被反复顶下来时互不覆盖。
fn 归档名(键名: &str) -> String {
    let 纳秒 = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|时长| 时长.as_nanos())
        .unwrap_or(0);
    format!("{键名}.{纳秒}")
}

/// 原子落件：已存在且内容相同 ⇒ 直接交回（重入幂等）；否则写临时件再硬链发布。
fn 原子落件(落点目录: &Path, 键名: &str, 字节: &[u8]) -> Result<PathBuf, String> {
    let 落盘路径 = 落点目录.join(键名);
    if let Ok(已有) = fs::read(&落盘路径) {
        if 已有 == 字节 {
            return Ok(落盘路径);
        }
        return Err("同键已有不同内容，不覆盖".to_owned());
    }
    let (临时清理, 临时文件) = 建临时件(落点目录, 键名)?;
    use std::io::Write;
    let mut 句柄 = 临时文件;
    句柄
        .write_all(字节)
        .and_then(|()| 句柄.sync_all())
        .map_err(|错误| format!("创作临时件写入失败：{错误}"))?;
    drop(句柄);
    match fs::hard_link(&临时清理.临时路径, &落盘路径) {
        Ok(()) => {}
        Err(错误) if 错误.kind() == std::io::ErrorKind::AlreadyExists => {}
        Err(错误) => return Err(format!("创作件原子发布失败：{错误}")),
    }
    Ok(落盘路径)
}

/// 临时件清理守卫：无论走哪条路退出，临时件都不留。
struct 临时清理 {
    临时路径: PathBuf,
}

impl Drop for 临时清理 {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.临时路径);
    }
}

/// 建一个不撞名的临时件（`.临时` 后缀 ⇒ 停机恢复能识别出中断残件）。
fn 建临时件(落点目录: &Path, 键名: &str) -> Result<(临时清理, fs::File), String> {
    let 纳秒 = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|错误| format!("创作临时件时钟读取失败：{错误}"))?
        .as_nanos();
    for 临时序号 in 0..128 {
        let 临时路径 = 落点目录.join(format!(
            ".{键名}.{}.{纳秒}.{临时序号}{临时件后缀}",
            std::process::id()
        ));
        match fs::OpenOptions::new().write(true).create_new(true).open(&临时路径) {
            Ok(临时文件) => return Ok((临时清理 { 临时路径 }, 临时文件)),
            Err(错误) if 错误.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(错误) => return Err(format!("创作临时件创建失败：{错误}")),
        }
    }
    Err("创作临时件名称竞争次数超限".to_owned())
}

#[cfg(test)]
mod 发布阶段测试 {
    use super::*;

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
            let 纳秒 = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
            let 目录根 = std::env::temp_dir()
                .canonicalize()
                .unwrap()
                .join(format!("发布阶段验证-{}-{纳秒}-{临时序号}", std::process::id()));
            match fs::create_dir(&目录根) {
                Ok(()) => return 测试目录 { 目录根 },
                Err(错误) if 错误.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(错误) => panic!("创建测试目录失败：{错误}"),
            }
        }
        panic!("测试目录竞争次数超限")
    }

    #[test]
    fn 四类发布阶段_名字两两不同_次序与判别值一致() {
        for (序号, 阶段) in 发布阶段::全集.iter().enumerate() {
            assert_eq!(*阶段 as usize, 序号, "次序必须与判别值一致：{阶段:?}");
        }
        for (前项序, 前项) in 发布阶段::全集.iter().enumerate() {
            for 后项 in &发布阶段::全集[前项序 + 1..] {
                assert_ne!(前项.取名称(), 后项.取名称(), "目录名不许重复");
            }
        }
    }

    #[test]
    fn 四类阶段目录路径两两不同() {
        let 测试根 = 创建测试目录();
        let 发布根 = 测试根.目录根.join("候选发布");
        let 路径表: Vec<PathBuf> = 发布阶段::全集
            .iter()
            .map(|阶段| 阶段目录路径(&发布根, *阶段))
            .collect();
        for (前项序, 前项) in 路径表.iter().enumerate() {
            for 后项 in &路径表[前项序 + 1..] {
                assert_ne!(前项, 后项, "四类目录不许重合");
            }
        }
    }

    #[test]
    fn 阶段目录路径只拼不建() {
        let 测试根 = 创建测试目录();
        let 发布根 = 测试根.目录根.join("候选发布");
        let 路径 = 阶段目录路径(&发布根, 发布阶段::发布);
        assert_eq!(路径, 发布根.join("发布"));
        assert!(!路径.exists(), "只拼路径不该建目录");
    }

    #[test]
    fn 确保阶段目录真建得出来() {
        let 测试根 = 创建测试目录();
        let 发布根 = 测试根.目录根.join("候选发布");
        for 阶段 in 发布阶段::全集 {
            let 路径 = 确保阶段目录(&发布根, 阶段).expect("建目录");
            assert!(路径.is_dir(), "{阶段:?} 目录该真建出来");
            assert_eq!(路径, 发布根.join(阶段.取名称()));
        }
    }

    #[test]
    fn 创作件原子落盘且重入同路径() {
        let 测试根 = 创建测试目录();
        let 发布根 = 测试根.目录根.join("候选发布");
        let 字节 = b"candidate-payload";
        let 首次 = 落创作件(&发布根, "某件", 字节).unwrap();
        let 再次 = 落创作件(&发布根, "某件", 字节).unwrap();
        assert_eq!(首次, 再次, "同键重入必须交回同一路径");
        assert_eq!(fs::read(&首次).unwrap(), 字节);
        assert_eq!(首次.parent(), Some(阶段目录路径(&发布根, 发布阶段::创作).as_path()));
        let 创作目录 = 阶段目录路径(&发布根, 发布阶段::创作);
        assert_eq!(fs::read_dir(&创作目录).unwrap().count(), 1, "临时件不该留下");
    }

    #[test]
    fn 晋级把旧件挪进旧版本() {
        let 测试根 = 创建测试目录();
        let 发布根 = 测试根.目录根.join("候选发布");
        落待验件(&发布根, "某件", b"version-1").unwrap();
        let 发布路径 = 晋级到发布(&发布根, "某件").unwrap();
        assert_eq!(fs::read(&发布路径).unwrap(), b"version-1");
        let 旧版本目录 = 阶段目录路径(&发布根, 发布阶段::旧版本);
        assert!(!旧版本目录.exists(), "首次晋级没有旧件要归档");
        落待验件(&发布根, "某件", b"version-2").unwrap();
        let 发布路径 = 晋级到发布(&发布根, "某件").unwrap();
        assert_eq!(fs::read(&发布路径).unwrap(), b"version-2");
        let 归档表: Vec<_> = fs::read_dir(&旧版本目录).unwrap().flatten().collect();
        assert_eq!(归档表.len(), 1, "被顶下来的那一份该进旧版本目录");
        assert_eq!(fs::read(归档表[0].path()).unwrap(), b"version-1");
        let 待验目录 = 阶段目录路径(&发布根, 发布阶段::待验);
        assert_eq!(fs::read_dir(&待验目录).unwrap().count(), 0, "晋级后待验目录该空");
    }

    #[test]
    fn 解析不出根不落源码树() {
        let 测试根 = 创建测试目录();
        let 发布根 = 测试根.目录根.join("候选发布");
        assert!(落待验件(&发布根, "缺件", b"payload").is_ok());
        assert!(晋级到发布(&发布根, "不存在的那一份").is_err(), "待验目录没有就不晋级");
        assert!(原子落件(&发布根, "同键异内容", b"payload-a").is_ok());
        assert!(原子落件(&发布根, "同键异内容", b"payload-b").is_err(), "同键异内容不覆盖");
    }
}
