//! 装载件缓存 —— 能力包件解包物的**仓外落点**（与 `开发工具/取证/声明记录区反解/运行数据根.py`
//! 同形：可丢 · 可重建 · 丢了关缓存照常算）。
//!
//! # 为什么在这里
//!
//! 底座装载支持库要 `dlopen` **本机机器码**，而制品（`.支持库制品`）是**能力包件** —— 拿它直接
//! `dlopen` 必失败（`扫扩展根.rs` 文件头）。所以装载前的必经一步是：按容器解包（
//! `v1_contract::容器`，唯一 codec）取**能力码段**字节 → 落一份**真文件** → 再 `dlopen`。
//!
//! 落点**不许**是源码树（`README.md` §十 · 判据 ⑳）也**不许**自拼路径（判据 ㉕）⇒ 唯一落点是
//! **运行数据根**的**缓存**类。`对外接口面` 按层序拿不到 `运行内核/运行数据根`（跳层）
//! ⇒ 由本层（它唯一的腿）提供这一口。
//!
//! # 解析不出根
//!
//! [`默认缓存根目录`] 返回 `None`（**不退回源码树、不退回 `/tmp`**）—— 调用方据此把它当
//! **结构化失败**报出（该子目录剔除并报因），绝不静默落进源码树。

use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use v1_contract::容器;
use v1_dataroot::{子目录, 子目录路径, 解析当前环境};

/// 缓存子目录名（`<运行数据根>/缓存/<本名>`）—— 固定，不随界面语言变（目录名是事实，不是文案）。
const 缓存子目录名: &str = "扩展装载";

struct 临时件清理 {
    临时路径: PathBuf,
}

impl Drop for 临时件清理 {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.临时路径);
    }
}

/// 默认缓存根目录 = `<运行数据根>/缓存/扩展装载`。
///
/// 解析不出根 ⇒ `None`（部署侧可用 `服务::缓存根` 覆盖，见 `网关.rs`）。
pub fn 默认缓存根目录() -> Option<PathBuf> {
    let 根目录 = 解析当前环境().ok()?;
    Some(子目录路径(&根目录, 子目录::缓存).join(缓存子目录名))
}

/// 读制品 → 校验段指纹 → 支持库能力码段落缓存（键 = 能力码内容指纹）⇒ 交回落盘路径。
///
/// 失败一律给一句可读原因（与 `取扩展声明` 同形）：扫描面上「这一个子目录不是可装载件」是
/// **正常结局**，不该中断别的子目录。
pub fn 解包到缓存(制品路径: &Path, 缓存根目录: &Path) -> Result<PathBuf, String> {
    let 制品字节 = fs::read(制品路径).map_err(|错误| format!("读不到制品：{错误}"))?;
    let 三段 = 容器::解包(&制品字节).map_err(|错误| format!("不是能力包件：{错误:?}"))?;
    if 容器::校验段指纹(&制品字节) != Some(true) {
        return Err("制品段指纹缺失、损坏或与内容不符".to_owned());
    }
    let 本体段头 = 容器::文件头魔数.len() + 容器::段头长度 + 三段.接口说明段.len();
    if 制品字节.get(本体段头 + 0x0B) != Some(&容器::段类型_能力码)
        || 三段.能力码段.is_empty()
    {
        return Err("本体不是非空的支持库能力码段，不进 dlopen".to_owned());
    }
    let 键名: String = 容器::算指纹(&三段.能力码段)
        .iter().map(|字节| format!("{字节:02x}")).collect();
    验证缓存目录(缓存根目录)?;
    fs::create_dir_all(缓存根目录).map_err(|错误| format!("建不出缓存目录：{错误}"))?;
    验证缓存目录(缓存根目录)?;
    let 落盘路径 = 缓存根目录.join(&键名);
    if 验证缓存件(&落盘路径, &三段.能力码段)? {
        return Ok(落盘路径);
    }
    let (临时清理, mut 临时文件) = 创建缓存临时件(缓存根目录, &键名)?;
    临时文件.write_all(&三段.能力码段)
        .and_then(|_| 临时文件.sync_all())
        .map_err(|错误| format!("缓存临时件写入或同步失败：{错误}"))?;
    drop(临时文件);
    验证缓存目录(缓存根目录)?;
    match fs::hard_link(&临时清理.临时路径, &落盘路径) {
        Ok(()) => {}
        Err(错误) if 错误.kind() == std::io::ErrorKind::AlreadyExists => {}
        Err(错误) => return Err(format!("缓存原子发布失败：{错误}")),
    }
    if !验证缓存件(&落盘路径, &三段.能力码段)? {
        return Err("发布后的缓存件不存在".to_owned());
    }
    Ok(落盘路径)
}

fn 验证缓存目录(缓存根目录: &Path) -> Result<(), String> {
    for 目录路径 in 缓存根目录.ancestors() {
        if 目录路径.as_os_str().is_empty() {
            continue;
        }
        match fs::symlink_metadata(目录路径) {
            Ok(目录属性) if 目录属性.is_dir() && !目录属性.file_type().is_symlink() => {}
            Ok(_) => return Err(format!("缓存目录链含符号链接或非目录：{}", 目录路径.display())),
            Err(错误) if 错误.kind() == std::io::ErrorKind::NotFound => {}
            Err(错误) => return Err(format!("缓存目录检查失败：{错误}")),
        }
    }
    Ok(())
}

fn 验证缓存件(落盘路径: &Path, 能力码段: &[u8]) -> Result<bool, String> {
    let 缓存属性 = match fs::symlink_metadata(落盘路径) {
        Ok(缓存属性) => 缓存属性,
        Err(错误) if 错误.kind() == std::io::ErrorKind::NotFound => return Ok(false),
        Err(错误) => return Err(format!("缓存件检查失败：{错误}")),
    };
    if !缓存属性.is_file() || 缓存属性.file_type().is_symlink() {
        return Err("缓存目标是符号链接或非普通文件".to_owned());
    }
    if 缓存属性.len() != 能力码段.len() as u64 {
        return Err("已有缓存件长度与能力码不符".to_owned());
    }
    let mut 打开选项 = fs::OpenOptions::new();
    打开选项.read(true);
    #[cfg(any(target_os = "linux", target_os = "android"))]
    {
        use std::os::unix::fs::OpenOptionsExt;
        打开选项.custom_flags(0x20000);
    }
    #[cfg(target_vendor = "apple")]
    {
        use std::os::unix::fs::OpenOptionsExt;
        打开选项.custom_flags(0x100);
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        打开选项.custom_flags(0x00200000);
    }
    let 缓存文件 = 打开选项.open(落盘路径)
        .map_err(|错误| format!("缓存件打开失败：{错误}"))?;
    let 打开属性 = 缓存文件.metadata().map_err(|错误| format!("缓存句柄检查失败：{错误}"))?;
    if !打开属性.is_file() {
        return Err("缓存句柄不是普通文件".to_owned());
    }
    let mut 缓存字节 = Vec::new();
    缓存文件.take(能力码段.len() as u64 + 1).read_to_end(&mut 缓存字节)
        .map_err(|错误| format!("缓存件读取失败：{错误}"))?;
    let 复核属性 = fs::symlink_metadata(落盘路径)
        .map_err(|错误| format!("缓存件复核失败：{错误}"))?;
    if !复核属性.is_file() || 复核属性.file_type().is_symlink() || 缓存字节 != 能力码段 {
        return Err("已有缓存件内容不符或目标被替换".to_owned());
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if 打开属性.dev() != 复核属性.dev() || 打开属性.ino() != 复核属性.ino() {
            return Err("缓存件读取期间目标被替换".to_owned());
        }
    }
    Ok(true)
}

fn 创建缓存临时件(缓存根目录: &Path, 键名: &str) -> Result<(临时件清理, fs::File), String> {
    let 时间戳 = SystemTime::now().duration_since(UNIX_EPOCH)
        .map_err(|错误| format!("临时件时钟读取失败：{错误}"))?.as_nanos();
    for 临时序号 in 0..128 {
        let 临时路径 = 缓存根目录.join(format!(
            ".{键名}.{}.{时间戳}.{临时序号}.临时", std::process::id()
        ));
        match fs::OpenOptions::new().write(true).create_new(true).open(&临时路径) {
            Ok(临时文件) => return Ok((临时件清理 { 临时路径 }, 临时文件)),
            Err(错误) if 错误.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(错误) => return Err(format!("缓存临时件创建失败：{错误}")),
        }
    }
    Err("缓存临时件名称竞争次数超限".to_owned())
}

#[cfg(test)]
mod 缓存测试 {
    use super::*;
    use std::sync::{Arc, Barrier};

    struct 测试目录 { 目录根: PathBuf }
    impl Drop for 测试目录 {
        fn drop(&mut self) { let _ = fs::remove_dir_all(&self.目录根); }
    }
    fn 创建测试目录() -> 测试目录 {
        for 临时序号 in 0..128 {
            let 时间戳 = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
            let 目录根 = std::env::temp_dir().canonicalize().unwrap()
                .join(format!("装载件缓存验证-{}-{时间戳}-{临时序号}", std::process::id()));
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
        let 缓存键: String = 容器::算指纹(代码字节).iter()
            .map(|字节| format!("{字节:02x}")).collect();
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
        for 制品字节 in [容器::装包(b"interface", 代码字节), 容器::装包(b"changed", 代码字节)] {
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
        for 工作线程 in 线程列表 { assert_eq!(工作线程.join().unwrap(), 目标路径); }
        assert_eq!(fs::read(&目标路径).unwrap(), 代码字节);
        assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 1);
    }

    #[test]
    fn 损坏旧缓存及非文件拒绝() {
        let 测试目录 = 创建测试目录();
        let 缓存目录 = 测试目录.目录根.join("缓存");
        fs::create_dir(&缓存目录).unwrap();
        let 制品文件 = 写测试制品(&测试目录.目录根, &容器::装包(b"interface", b"native-code"));
        let 目标路径 = 缓存键路径(&缓存目录, b"native-code");
        for 缓存字节 in [b"broken-code".as_slice(), b"".as_slice()] {
            fs::write(&目标路径, 缓存字节).unwrap();
            assert!(解包到缓存(&制品文件, &缓存目录).is_err());
            assert_eq!(fs::read(&目标路径).unwrap(), 缓存字节);
        }
        fs::remove_file(&目标路径).unwrap();
        fs::create_dir(&目标路径).unwrap();
        assert!(解包到缓存(&制品文件, &缓存目录).is_err());
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
}
