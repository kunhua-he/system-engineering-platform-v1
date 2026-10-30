//! 演示文稿的各个 OOXML 部件：单页、母版、空白版式、主题。
//!
//! 只覆盖 PowerPoint/WPS 都能打开的最小部件集（母版 + 空白版式 + 主题 + 每页一张），
//! 不做图片、图表、动画、SmartArt —— 这些不在契约里，就不假装能生成。
//! 文本按块落成独立文本框：**第一块当标题（32 磅加粗），其余当正文（18 磅）**。

use crate::演示文稿生成::幻灯片输入;

pub(crate) const 标题字号: i32 = 3200; // PPTX 字号单位是百分之一磅
const 正文字号: i32 = 1800;
/// XML 文本转义：只转必须转的五个，其余原样（避免把中文转成实体）
pub(crate) fn 转义(原文: &str) -> String {
    let mut 结果 = String::with_capacity(原文.len());
    for 单字 in 原文.chars() {
        match 单字 {
            '&' => 结果.push_str("&amp;"),
            '<' => 结果.push_str("&lt;"),
            '>' => 结果.push_str("&gt;"),
            '"' => 结果.push_str("&quot;"),
            '\'' => 结果.push_str("&apos;"),
            换行 => 结果.push(换行),
        }
    }
    结果
}

/// 一个文本框：块内每行落成一个 `<a:p>`，空行跳过
pub(crate) fn 文本框片段(标识号: u32, 文本: &str, 纵位EMU: i64, 字号: i32, 加粗: bool) -> String {
    let 粗体位 = if 加粗 { " b=\"1\"" } else { "" };
    let mut 段落 = String::new();
    for 行 in 文本.split('\n') {
        let 干净 = 行.trim();
        if 干净.is_empty() {
            continue;
        }
        段落.push_str(&format!(
            "<a:p><a:r><a:rPr lang=\"zh-CN\" sz=\"{}\"{}><a:solidFill><a:srgbClr val=\"262626\"/></a:solidFill></a:rPr><a:t>{}</a:t></a:r></a:p>",
            字号, 粗体位, 转义(干净)
        ));
    }
    if 段落.is_empty() {
        return String::new();
    }
    format!(
        "<p:sp><p:nvSpPr><p:cNvPr id=\"{}\" name=\"文本框{}\"/><p:cNvSpPr txBox=\"1\"/><p:nvPr/></p:nvSpPr>\
         <p:spPr><a:xfrm><a:off x=\"609600\" y=\"{}\"/><a:ext cx=\"10972800\" cy=\"914400\"/></a:xfrm>\
         <a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>\
         <p:txBody><a:bodyPr wrap=\"square\" lIns=\"91440\" tIns=\"45720\" rIns=\"91440\" bIns=\"45720\"><a:noAutofit/></a:bodyPr>\
         <a:lstStyle/>{}</p:txBody></p:sp>",
        标识号, 标识号, 纵位EMU, 段落
    )
}

pub(crate) fn 单页XML(页: &幻灯片输入, 页序: usize) -> String {
    let mut 形状片段 = String::new();
    let mut 纵位 = 457200i64;
    let mut 标识号 = 2u32;
    // 标题先落：用了块列表第一项还是单独的 `标题` 字段，由调用方决定，这里只管排版
    if !页.标题.trim().is_empty() {
        形状片段.push_str(&文本框片段(标识号, &页.标题, 纵位, 标题字号, true));
        标识号 += 1;
        纵位 += 1188720;
    }
    for 块 in &页.文本块 {
        形状片段.push_str(&文本框片段(标识号, 块, 纵位, 正文字号, false));
        标识号 += 1;
        纵位 += 914400;
    }
    format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\
         <p:sld xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" \
         xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" \
         xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\">\
         <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"页{}\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>\
         <p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>\
         {}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>",
        页序 + 1, 形状片段
    )
}

pub(crate) fn 母版XML() -> String {
    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\
     <p:sldMaster xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" \
     xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" \
     xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\">\
     <p:cSld><p:bg><p:bgRef idx=\"1001\"><a:schemeClr val=\"bg1\"/></p:bgRef></p:bg>\
     <p:spTree><p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"母版\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>\
     <p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>\
     </p:spTree></p:cSld>\
     <p:clrMap bg1=\"lt1\" tx1=\"dk1\" bg2=\"lt2\" tx2=\"dk2\" accent1=\"accent1\" accent2=\"accent2\" \
     accent3=\"accent3\" accent4=\"accent4\" accent5=\"accent5\" accent6=\"accent6\" hlink=\"hlink\" folHlink=\"folHlink\"/>\
     <p:sldLayoutIdLst><p:sldLayoutId id=\"2147483649\" r:id=\"rId1\"/></p:sldLayoutIdLst>\
     </p:sldMaster>".to_string()
}

pub(crate) fn 版式XML() -> String {
    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\
     <p:sldLayout xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" \
     xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" \
     xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" type=\"blank\" preserve=\"1\">\
     <p:cSld name=\"空白\"><p:spTree><p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"版式\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>\
     <p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>\
     </p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>".to_string()
}

pub(crate) fn 主题XML() -> String {
    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\
     <a:theme xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" name=\"默认主题\">\
     <a:themeElements>\
     <a:clrScheme name=\"默认\"><a:dk1><a:sysClr val=\"windowText\" lastClr=\"000000\"/></a:dk1>\
     <a:lt1><a:sysClr val=\"window\" lastClr=\"FFFFFF\"/></a:lt1>\
     <a:dk2><a:srgbClr val=\"44546A\"/></a:dk2><a:lt2><a:srgbClr val=\"E7E6E6\"/></a:lt2>\
     <a:accent1><a:srgbClr val=\"4472C4\"/></a:accent1><a:accent2><a:srgbClr val=\"ED7D31\"/></a:accent2>\
     <a:accent3><a:srgbClr val=\"A5A5A5\"/></a:accent3><a:accent4><a:srgbClr val=\"FFC000\"/></a:accent4>\
     <a:accent5><a:srgbClr val=\"5B9BD5\"/></a:accent5><a:accent6><a:srgbClr val=\"70AD47\"/></a:accent6>\
     <a:hlink><a:srgbClr val=\"0563C1\"/></a:hlink><a:folHlink><a:srgbClr val=\"954F72\"/></a:folHlink></a:clrScheme>\
     <a:fontScheme name=\"默认\"><a:majorFont><a:latin typeface=\"Calibri\"/><a:ea typeface=\"\"/><a:cs typeface=\"\"/></a:majorFont>\
     <a:minorFont><a:latin typeface=\"Calibri\"/><a:ea typeface=\"\"/><a:cs typeface=\"\"/></a:minorFont></a:fontScheme>\
     <a:fmtScheme name=\"默认\"><a:fillStyleLst>\
     <a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>\
     <a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>\
     <a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:fillStyleLst>\
     <a:lnStyleLst><a:ln><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln>\
     <a:ln><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln>\
     <a:ln><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln></a:lnStyleLst>\
     <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle>\
     <a:effectStyle><a:effectLst/></a:effectStyle>\
     <a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>\
     <a:bgFillStyleLst><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>\
     <a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>\
     <a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:bgFillStyleLst>\
     </a:fmtScheme></a:themeElements></a:theme>".to_string()
}

