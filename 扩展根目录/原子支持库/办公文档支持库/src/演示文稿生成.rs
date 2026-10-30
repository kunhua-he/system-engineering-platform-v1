//! 演示文稿生成：由「页表 + 每页文本块」打包写出最小可用的 .pptx。
//!
//! 不做图片、图表、动画、SmartArt —— 这些不在契约里，就不假装能生成。

use std::io::Write;

use crate::编号与码面::错误码;
use crate::演示文稿部件::{单页XML, 版式XML, 母版XML, 主题XML};

/// 单页输入：标题 + 正文文本块（顺序即落版顺序）
pub(crate) struct 幻灯片输入 {
    pub 标题: String,
    pub 文本块: Vec<String>,
}

const 默认页宽磅: f64 = 960.0;
const 默认页高磅: f64 = 540.0;

fn 磅转EMU(磅值: f64) -> i64 {
    (磅值 * 12700.0).round() as i64
}

/// 打包写出 .pptx；返回字节数。输出路径必须是绝对路径（不按 cwd 解释）。
pub(crate) fn 生成演示文稿(
    页宽磅: Option<f64>,
    页高磅: Option<f64>,
    页表: &[幻灯片输入],
    输出路径: &str,
) -> Result<u64, u32> {
    if !输出路径.starts_with('/') {
        return Err(错误码::参数不合法);
    }
    if 页表.is_empty() || 页表.len() > 500 {
        return Err(错误码::参数不合法);
    }
    let 宽 = 页宽磅.unwrap_or(默认页宽磅);
    let 高 = 页高磅.unwrap_or(默认页高磅);
    if !(1.0..=3000.0).contains(&宽) || !(1.0..=3000.0).contains(&高) {
        return Err(错误码::参数不合法);
    }
    let 宽EMU = 磅转EMU(宽);
    let 高EMU = 磅转EMU(高);
    let 页数 = 页表.len();

    // 版本号用 15（PowerPoint 2013+ 口径），兼容旧版读 14 也能开
    let mut 页标识 = String::new();
    let mut 关系项 = String::new();
    for 页序 in 0..页数 {
        页标识.push_str(&format!("<p:sldId id=\"{}\" r:id=\"rId{}\"/>", 256 + 页序, 页序 + 2));
        关系项.push_str(&format!(
            "<Relationship Id=\"rId{}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide\" Target=\"slides/slide{}.xml\"/>",
            页序 + 2, 页序 + 1
        ));
    }
    let 总页XML = format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\
         <p:presentation xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" \
         xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" \
         xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" saveSubsetFonts=\"1\">\
         <p:sldMasterIdLst><p:sldMasterId id=\"2147483648\" r:id=\"rId1\"/></p:sldMasterIdLst>\
         <p:sldIdLst>{}</p:sldIdLst>\
         <p:sldSz cx=\"{}\" cy=\"{}\" type=\"custom\"/><p:notesSz cx=\"6858000\" cy=\"9144000\"/>\
         </p:presentation>",
        页标识, 宽EMU, 高EMU
    );
    let 总关系XML = format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\
         <Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">\
         <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster\" Target=\"slideMasters/slideMaster1.xml\"/>\
         {}</Relationships>",
        关系项
    );
    let 根关系XML = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\
        <Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">\
        <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"ppt/presentation.xml\"/>\
        </Relationships>";
    let 母版关系XML = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\
        <Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">\
        <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout\" Target=\"../slideLayouts/slideLayout1.xml\"/>\
        <Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme\" Target=\"../theme/theme1.xml\"/>\
        </Relationships>";
    let 版式关系XML = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\
        <Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">\
        <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster\" Target=\"../slideMasters/slideMaster1.xml\"/>\
        </Relationships>";
    let mut 类型项 = String::new();
    for 页序 in 0..页数 {
        类型项.push_str(&format!(
            "<Override PartName=\"/ppt/slides/slide{}.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slide+xml\"/>",
            页序 + 1
        ));
    }
    let 类型XML = format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\
         <Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">\
         <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>\
         <Default Extension=\"xml\" ContentType=\"application/xml\"/>\
         <Override PartName=\"/ppt/presentation.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml\"/>\
         <Override PartName=\"/ppt/slideMasters/slideMaster1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml\"/>\
         <Override PartName=\"/ppt/slideLayouts/slideLayout1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml\"/>\
         <Override PartName=\"/ppt/theme/theme1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.theme+xml\"/>\
         {}</Types>",
        类型项
    );

    let 源文件 = std::fs::File::create(输出路径).map_err(|_| 错误码::写出失败)?;
    let mut 压缩包 = zip::ZipWriter::new(源文件);
    let 打包参数 = zip::write::SimpleFileOptions::default();
    let 固定件: [(&str, &str); 7] = [
        ("[Content_Types].xml", 类型XML.as_str()),
        ("_rels/.rels", 根关系XML),
        ("ppt/presentation.xml", 总页XML.as_str()),
        ("ppt/_rels/presentation.xml.rels", 总关系XML.as_str()),
        ("ppt/slideMasters/slideMaster1.xml", &母版XML()),
        ("ppt/slideMasters/_rels/slideMaster1.xml.rels", 母版关系XML),
        ("ppt/slideLayouts/slideLayout1.xml", &版式XML()),
    ];
    for (条目名, 条目内容) in 固定件 {
        压缩包.start_file(条目名, 打包参数).map_err(|_| 错误码::写出失败)?;
        压缩包.write_all(条目内容.as_bytes()).map_err(|_| 错误码::写出失败)?;
    }
    let 版式关系条 = ("ppt/slideLayouts/_rels/slideLayout1.xml.rels", 版式关系XML);
    压缩包.start_file(版式关系条.0, 打包参数).map_err(|_| 错误码::写出失败)?;
    压缩包.write_all(版式关系条.1.as_bytes()).map_err(|_| 错误码::写出失败)?;
    let 主题文本 = 主题XML();
    压缩包.start_file("ppt/theme/theme1.xml", 打包参数).map_err(|_| 错误码::写出失败)?;
    压缩包.write_all(主题文本.as_bytes()).map_err(|_| 错误码::写出失败)?;
    for (页序, 页) in 页表.iter().enumerate() {
        压缩包.start_file(format!("ppt/slides/slide{}.xml", 页序 + 1), 打包参数)
            .map_err(|_| 错误码::写出失败)?;
        压缩包.write_all(单页XML(页, 页序).as_bytes()).map_err(|_| 错误码::写出失败)?;
        let 页关系 = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\
             <Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">\
             <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout\" Target=\"../slideLayouts/slideLayout1.xml\"/>\
             </Relationships>";
        压缩包.start_file(format!("ppt/slides/_rels/slide{}.xml.rels", 页序 + 1), 打包参数)
            .map_err(|_| 错误码::写出失败)?;
        压缩包.write_all(页关系.as_bytes()).map_err(|_| 错误码::写出失败)?;
    }
    压缩包.finish().map_err(|_| 错误码::写出失败)?;
    let 字节数 = std::fs::metadata(输出路径).map(|元数据项| 元数据项.len()).unwrap_or(0);
    Ok(字节数)
}

#[cfg(test)]
mod 测试 {
    use super::*;

    fn 样例页表() -> Vec<幻灯片输入> {
        vec![
            幻灯片输入 {
                标题: "第一页标题".to_string(),
                文本块: vec!["正文第一行".to_string(), "正文第二行
第二段".to_string()],
            },
            幻灯片输入 {
                标题: "第二页标题".to_string(),
                文本块: Vec::new(),
            },
        ]
    }

    #[test]
    fn 生成最小演示文稿() {
        // 固定落 /tmp：temp_dir() 是本进程的 TMPDIR（Hermes 会话里指到 scratch），外部验证脚本找不到
        let 路径 = "/tmp/v1生成测试.pptx".to_string();
        let 字节数 = 生成演示文稿(Some(960.0), None, &样例页表(), &路径).expect("生成失败");
        assert!(字节数 > 3000, "产出太小，怀疑部件没写全：{字节数}");
        println!("产出 {路径} {字节数} 字节");
    }

    #[test]
    fn 相对输出路径被拒() {
        assert!(生成演示文稿(None, None, &样例页表(), "相对路径.pptx").is_err());
    }

    #[test]
    fn 空页表被拒() {
        assert!(生成演示文稿(None, None, &[], "/tmp/空.pptx").is_err());
    }

    #[test]
    fn 尺寸越界被拒() {
        assert!(生成演示文稿(Some(0.5), None, &样例页表(), "/tmp/越界.pptx").is_err());
    }
}
