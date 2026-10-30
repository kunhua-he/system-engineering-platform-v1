//! 案例与制品共用运行态仓根；编译缓存不携带被验工作树身份。
use std::path::{Path, PathBuf};

pub fn 定位当前仓根() -> Result<PathBuf, String> {
    let 当前目录 = std::env::current_dir().map_err(|错误|format!("读取运行目录失败：{错误}"))?;
    从运行目录定位(&当前目录)
}

fn 从运行目录定位(当前目录: &Path) -> Result<PathBuf, String> {
    for 目录项 in 当前目录.ancestors() {
        if 目录项.join("Cargo.toml").is_file()
            && 目录项.join("扩展装载/扩展根声明.json").is_file()
            && 目录项.join("测试验证/测试案例").is_dir() {
            return Ok(目录项.to_path_buf());
        }
    }
    Err(format!("运行目录 {} 不在有效V1工作树内；请从目标仓库或其子目录运行案例程序", 当前目录.display()))
}

#[cfg(test)]
mod 测试 {
    use super::从运行目录定位;
    #[test]
    fn 同一定位逻辑随运行树切换且拒绝树外() {
        let 缓存根 = std::env::temp_dir().join(format!("案例根定位-{}-{}",std::process::id(),std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
        std::fs::create_dir_all(&缓存根).unwrap();
        for 树名 in ["施工工作树1", "施工工作树2"] {
            let 施工根 = 缓存根.join(树名);
            std::fs::create_dir_all(施工根.join("扩展装载")).unwrap();
            std::fs::create_dir_all(施工根.join("测试验证/测试案例/跑案例")).unwrap();
            std::fs::write(施工根.join("Cargo.toml"), "[workspace]").unwrap();
            std::fs::write(施工根.join("扩展装载/扩展根声明.json"), "{}").unwrap();
            assert_eq!(从运行目录定位(&施工根).unwrap(),施工根);
            assert_eq!(从运行目录定位(&施工根.join("测试验证/测试案例/跑案例")).unwrap(),施工根);
        }
        assert!(从运行目录定位(&缓存根).is_err());
        std::fs::remove_dir_all(&缓存根).unwrap();
    }
}
