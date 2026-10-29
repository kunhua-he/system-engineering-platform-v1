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
