//! 装载件缓存 · 加固单测：候选择源 / 读制品有上限 / 权限位过宽 三条反向样本。

use super::取件判据::读制品有上限;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};
use v1_contract::容器;

use super::*;

struct 临时目录 {
    目录根: PathBuf,
}
impl Drop for 临时目录 {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.目录根);
    }
}
fn 建临时目录(标签: &str) -> 临时目录 {
    for 临时序号 in 0..128 {
        let 时间戳 = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let 目录根 = std::env::temp_dir()
            .canonicalize()
            .unwrap()
            .join(format!("装载件缓存加固-{标签}-{}-{时间戳}-{临时序号}", std::process::id()));
        match fs::create_dir(&目录根) {
            Ok(()) => return 临时目录 { 目录根 },
            Err(错误) if 错误.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(错误) => panic!("创建测试目录失败：{错误}"),
        }
    }
    panic!("测试目录竞争次数超限")
}
fn 写制品(目录根: &Path) -> (PathBuf, &'static [u8]) {
    let 代码字节: &'static [u8] = b"native-code";
    let 制品文件 = 目录根.join("样例.支持库制品");
    fs::write(&制品文件, 容器::装包(b"interface", 代码字节)).unwrap();
    (制品文件, 代码字节)
}

/// 候选择源：符号链接那一条跳过、真件那一条选中；全不可信时逐条报出拒因。
#[test]
fn 候选择源_全不可信时报出每一条拒因() {
    let 测试根 = 建临时目录("择源");
    let (真件, _) = 写制品(&测试根.目录根);
    let 全假件 = 测试根.目录根.join("假制品.支持库制品");
    assert_eq!(按候选择源(&[&全假件, &真件]).unwrap(), 真件.as_path(), "链件不参与时选中真件");
    #[cfg(unix)]
    {
        let 链件 = 测试根.目录根.join("链制品.支持库制品");
        std::os::unix::fs::symlink(&真件, &链件).unwrap();
        assert_eq!(按候选择源(&[&链件, &真件]).unwrap(), 真件.as_path(), "链件跳过、真件选中");
    }
    let 全不可信 = 按候选择源(&[&全假件]).unwrap_err();
    assert!(全不可信.contains("假制品"), "拒因要点名那一条路径：{全不可信}");
    assert!(按候选择源(&[]).unwrap_err().contains("空的"));
}

/// 读制品有上限：**先看元数据、过线就不读** —— 超限报因、未超限原样读回。
#[test]
fn 读制品有上限_超限不读未超限读回() {
    let 测试根 = 建临时目录("大小");
    let (制品文件, 代码字节) = 写制品(&测试根.目录根);
    let 超过本件长度 = 容器::装包(b"interface", 代码字节).len() as u64 - 1;
    let 拒因 = 读制品有上限(&制品文件, 超过本件长度).unwrap_err();
    assert!(拒因.contains("超过上限"), "该报超上限：{拒因}");
    assert_eq!(读制品有上限(&制品文件, 能力码字节上限).unwrap().len() as u64, 超过本件长度 + 1);
}

/// 权限位过宽：组/他人可写的缓存件 ⇒ 拒（校验过的字节可能被第三方换掉）。
#[cfg(unix)]
#[test]
fn 权限位过宽即拒() {
    use std::os::unix::fs::PermissionsExt;
    let 测试根 = 建临时目录("权限");
    let 缓存目录 = 测试根.目录根.join("缓存");
    let (制品文件, _) = 写制品(&测试根.目录根);
    let 落点 = 解包到缓存(&制品文件, &缓存目录).unwrap();
    let mut 权限 = fs::metadata(&落点).unwrap().permissions();
    权限.set_mode(0o666);
    fs::set_permissions(&落点, 权限).unwrap();
    let 拒因 = 解包到缓存(&制品文件, &缓存目录).unwrap_err();
    assert!(拒因.contains("权限位过宽"), "该报权限位过宽：{拒因}");
}
