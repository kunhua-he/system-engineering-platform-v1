//! 模块接口说明组：条数及逐项长度小端编码；单条六字段仍复用父件。
use alloc::{collections::BTreeSet, vec::Vec};
use super::{接口说明, 读游标, 编码, 解码};

pub fn 编码接口组(说明表: &[接口说明]) -> Option<Vec<u8>> {
    if 说明表.is_empty() { return None; }
    let 条数 = u32::try_from(说明表.len()).ok()?;
    let mut 已有编号 = BTreeSet::new();
    let mut 输出缓冲 = Vec::new();
    输出缓冲.extend_from_slice(&条数.to_le_bytes());
    for 说明 in 说明表 {
        if !已有编号.insert(说明.编号) { return None; }
        let 单项字节 = 编码(说明);
        let 单项长度 = u32::try_from(单项字节.len()).ok()?;
        输出缓冲.extend_from_slice(&单项长度.to_le_bytes());
        输出缓冲.extend_from_slice(&单项字节);
    }
    Some(输出缓冲)
}

pub fn 解码接口组(字节: &[u8]) -> Option<Vec<接口说明>> {
    let mut 读游标 = 读游标 { 字节, 位偏移: 0 };
    let 条数 = 读游标.读四字节()? as usize;
    if 条数 == 0 || 条数 > 读游标.剩余字节()/4 { return None; }
    let mut 说明表 = Vec::with_capacity(条数);
    let mut 已有编号 = BTreeSet::new();
    for _ in 0..条数 {
        let 单项长度 = 读游标.读四字节()? as usize;
        let 说明 = 解码(读游标.取字节(单项长度)?)?;
        if !已有编号.insert(说明.编号) { return None; }
        说明表.push(说明);
    }
    if 读游标.剩余字节() != 0 { return None; }
    Some(说明表)
}

#[cfg(test)]
mod 测试 {
    use super::*;
    fn 示例说明(编号: u32) -> 接口说明 {
        接口说明 { 编号, 名称: alloc::format!("示例能力{编号}"), 说明: "组往返".into(), 参数表: Vec::new(), 返回类型: 1, 可抛错误码: Vec::new() }
    }
    #[test]
    fn 单项与多项逐字段往返() {
        for 条数 in [1, 3] {
            let 说明表: Vec<_> = (0..条数).map(示例说明).collect();
            assert_eq!(解码接口组(&编码接口组(&说明表).unwrap()).unwrap(), 说明表);
        }
    }
    #[test]
    fn 空组重复截断与尾部多余字节拒绝() {
        assert!(编码接口组(&[]).is_none());
        assert!(编码接口组(&[示例说明(1), 示例说明(1)]).is_none());
        assert!(解码接口组(&[0,0,0,0]).is_none());
        let mut 字节 = 编码接口组(&[示例说明(1)]).unwrap();
        for 末位 in 0..字节.len() { assert!(解码接口组(&字节[..末位]).is_none()); }
        字节.push(0); assert!(解码接口组(&字节).is_none());
        let mut 重复字节 = 编码接口组(&[示例说明(1), 示例说明(2)]).unwrap();
        let 第二偏移 = 12 + 编码(&示例说明(1)).len();
        重复字节[第二偏移..第二偏移+4].copy_from_slice(&1u32.to_le_bytes());
        assert!(解码接口组(&重复字节).is_none());
    }
}
