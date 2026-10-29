use super::受控读取面::读取受控头部;
#[test]
fn 测试受控头部正常空值与大件() {
    let 样本根 = std::env::temp_dir().join(format!("受控读取样本-{}",std::process::id()));
    std::fs::create_dir_all(&样本根).unwrap();
    std::fs::write(样本根.join("中文文件.txt"),vec![65_u8;1048580]).unwrap();
    assert_eq!(读取受控头部(样本根.to_str().unwrap(),"中文文件.txt",1048576).unwrap().len(),1048576);
    assert!(读取受控头部(样本根.to_str().unwrap(),"中文文件.txt",0).unwrap().is_empty());
    assert!(读取受控头部(样本根.to_str().unwrap(),"中文文件.txt",1048577).is_err());
    assert!(读取受控头部(样本根.to_str().unwrap(),"../越界文件",1).is_err());
    assert!(读取受控头部(样本根.to_str().unwrap(),"/绝对文件",1).is_err());
    assert!(读取受控头部(样本根.to_str().unwrap(),"缺失文件",1).is_err());
    assert!(读取受控头部(样本根.to_str().unwrap(),".",1).is_err());
    std::fs::write(样本根.join("空白文件"),b"").unwrap();
    assert!(读取受控头部(样本根.to_str().unwrap(),"空白文件",100).unwrap().is_empty());
    #[cfg(unix)] {
        std::os::unix::fs::symlink(样本根.join("中文文件.txt"),样本根.join("文件链接")).unwrap();
        std::os::unix::fs::symlink(&样本根,样本根.join("目录链接")).unwrap();
        assert!(读取受控头部(样本根.to_str().unwrap(),"文件链接",1).is_err());
        assert!(读取受控头部(样本根.to_str().unwrap(),"目录链接/中文文件.txt",1).is_err());
    }
    std::fs::remove_dir_all(样本根).unwrap();
}


#[test]
fn 测试受控整读不截断与上界拒绝() {
    use super::受控读取面::读取受控全件;
    let 样本根 = std::env::temp_dir().join(format!("受控整读样本-{}", std::process::id()));
    std::fs::create_dir_all(&样本根).unwrap();
    let 文件内容 = vec![71_u8; 5 * 1024 * 1024 + 1];
    std::fs::write(样本根.join("大件样本"), &文件内容).unwrap();
    assert_eq!(读取受控全件(样本根.to_str().unwrap(), "大件样本", 文件内容.len() as i64).unwrap(), 文件内容);
    assert_eq!(读取受控全件(样本根.to_str().unwrap(), "大件样本", 1048576), Err(crate::错误码::资源受限));
    assert_eq!(读取受控全件(样本根.to_str().unwrap(), "大件样本", -1), Err(crate::错误码::资源受限));
    assert_eq!(读取受控全件(样本根.to_str().unwrap(), "大件样本", 52428801), Err(crate::错误码::资源受限));
    assert!(读取受控全件(样本根.to_str().unwrap(), "../越界文件", 4).is_err());
    assert!(读取受控全件(样本根.to_str().unwrap(), "缺失文件", 4).is_err());
    std::fs::write(样本根.join("空白样本"), b"").unwrap();
    assert_eq!(读取受控全件(样本根.to_str().unwrap(), "空白样本", 0).unwrap(), Vec::<u8>::new());
    #[cfg(unix)] {
        std::os::unix::fs::symlink(样本根.join("大件样本"), 样本根.join("文件链接")).unwrap();
        assert!(读取受控全件(样本根.to_str().unwrap(), "文件链接", 52428800).is_err());
    }
    std::fs::remove_dir_all(样本根).unwrap();
}


#[test]
#[cfg(unix)]
fn 测试原子覆盖与失败保留旧件() {
    use super::受控写入面::原子写入文本;
    use std::os::unix::fs::PermissionsExt;
    let 样本根 = std::env::temp_dir().join(format!("原子写入样本-{}", std::process::id()));
    std::fs::create_dir_all(&样本根).unwrap();
    let 目标文件 = 样本根.join("目录层/中文文本.txt");
    assert_eq!(原子写入文本(样本根.to_str().unwrap(), "目录层/中文文本.txt", "中文"), Ok(6));
    assert_eq!(std::fs::read_to_string(&目标文件).unwrap(), "中文");
    std::fs::set_permissions(&目标文件, std::fs::Permissions::from_mode(0o640)).unwrap();
    assert_eq!(原子写入文本(样本根.to_str().unwrap(), "目录层/中文文本.txt", "替换"), Ok(6));
    assert_eq!(std::fs::metadata(&目标文件).unwrap().permissions().mode() & 0o777, 0o640);
    assert!(原子写入文本(样本根.to_str().unwrap(), "目录层/中文文本.txt", &"X".repeat(131073)).is_err());
    assert_eq!(std::fs::read_to_string(&目标文件).unwrap(), "替换");
    assert!(原子写入文本(样本根.to_str().unwrap(), "../越界文件", "内容").is_err());
    std::os::unix::fs::symlink(&目标文件, 样本根.join("文件链接")).unwrap();
    assert!(原子写入文本(样本根.to_str().unwrap(), "文件链接", "坏覆盖").is_err());
    assert_eq!(std::fs::read_to_string(&目标文件).unwrap(), "替换");
    assert_eq!(原子写入文本(样本根.to_str().unwrap(), "目录层/中文文本.txt", ""), Ok(0));
    assert!(std::fs::read(&目标文件).unwrap().is_empty());
    assert_eq!(std::fs::read_dir(样本根.join("目录层")).unwrap().count(), 1);
    std::fs::remove_dir_all(样本根).unwrap();
}
