//! 向上找同名标记目录（3116）。

use crate::编号与码面::错误码;

use super::基础件::映射读错;


pub(super) fn 查找祖先行(
    起点路径: &std::path::Path, 标记字节: &[u8]
) -> Result<(u32, Vec<u8>), u32> {
    let 标记文本 = std::str::from_utf8(标记字节)
        .map_err(|_| 错误码::参数不合法)?
        .trim();
    if 标记文本.is_empty()
        || 标记文本.contains('/')
        || 标记文本.contains('\0')
        || 标记文本.len() > 255
    {
        return Err(错误码::参数不合法);
    }
    let 起点属性 = std::fs::symlink_metadata(起点路径).map_err(映射读错)?;
    let mut 当前路径 = if 起点属性.is_dir() {
        起点路径.to_path_buf()
    } else {
        起点路径
            .parent()
            .ok_or(错误码::未找到祖先目录)?
            .to_path_buf()
    };
    loop {
        let 名文本 = 当前路径.file_name().and_then(|末段| 末段.to_str());
        if 名文本 == Some(标记文本) {
            let 父路径 = 当前路径.parent().ok_or(错误码::未找到祖先目录)?;
            return Ok((4, 父路径.as_os_str().as_encoded_bytes().to_vec()));
        }
        if 当前路径.join(标记文本).is_dir() {
            return Ok((4, 当前路径.as_os_str().as_encoded_bytes().to_vec()));
        }
        match 当前路径.parent() {
            Some(父路径) => 当前路径 = 父路径.to_path_buf(),
            None => return Err(错误码::未找到祖先目录),
        }
    }
}


#[cfg(test)]
mod 祖先目录验证样本 {
    use super::*;
    use std::fs;

    fn 造样本根(唯一名: &str) -> std::path::PathBuf {
        let 样本根 =
            std::env::temp_dir().join(format!("v1祖先样本-{唯一名}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&样本根);
        fs::create_dir_all(样本根.join("MCP工具箱").join("运行时")).unwrap();
        fs::create_dir_all(样本根.join("其他")).unwrap();
        样本根
    }

    #[test]
    fn 查找祖先目录命中同名子目录() {
        let 样本根 = 造样本根("命中");
        let 起点目录 = 样本根.join("MCP工具箱").join("运行时");
        let (标签值, 返回字节) = 查找祖先行(&起点目录, "MCP工具箱".as_bytes()).unwrap();
        assert_eq!(标签值, 4);
        assert_eq!(
            std::path::Path::new(std::str::from_utf8(&返回字节).unwrap()),
            样本根
        );
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 查找祖先目录起点同名取父() {
        let 样本根 = 造样本根("同名");
        let 起点目录 = 样本根.join("MCP工具箱");
        let (_, 返回字节) = 查找祖先行(&起点目录, "MCP工具箱".as_bytes()).unwrap();
        assert_eq!(
            std::path::Path::new(std::str::from_utf8(&返回字节).unwrap()),
            样本根
        );
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 查找祖先目录找不到回码() {
        let 样本根 = 造样本根("落空");
        let 起点目录 = 样本根.join("其他");
        assert_eq!(
            查找祖先行(&起点目录, "不存在的标记".as_bytes()).unwrap_err(),
            错误码::未找到祖先目录
        );
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 查找祖先目录标记含分隔符被拒() {
        let 样本根 = 造样本根("分隔符");
        let 起点目录 = 样本根.join("其他");
        assert_eq!(
            查找祖先行(&起点目录, "上层/下层".as_bytes()).unwrap_err(),
            错误码::参数不合法
        );
        assert_eq!(
            查找祖先行(&起点目录, 空标记().as_bytes()).unwrap_err(),
            错误码::参数不合法
        );
        let _ = fs::remove_dir_all(&样本根);
    }

    #[test]
    fn 查找祖先目录起点不存在被拒() {
        let 样本根 = 造样本根("缺起点");
        let 起点目录 = 样本根.join("并没有这个目录");
        assert_eq!(
            查找祖先行(&起点目录, "MCP工具箱".as_bytes()).unwrap_err(),
            错误码::文件不存在
        );
        let _ = fs::remove_dir_all(&样本根);
    }

    fn 空标记() -> &'static str {
        ""
    }
}
