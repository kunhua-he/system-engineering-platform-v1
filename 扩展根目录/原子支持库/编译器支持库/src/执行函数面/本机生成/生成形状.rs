use crate::{语言面::形状错误, 语义::{名号表, 语义错误}};

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct 本机依赖 {
    pub 名称: Vec<u8>,
    pub 能力号: u16,
    pub 入参类型表: Vec<u32>,
    pub 返回类型: u32,
}

pub(crate) struct 本机生成请求<'请求> {
    pub 程序文本: &'请求 [u8],
    pub 命令表: &'请求 名号表,
    pub 常量表: &'请求 名号表,
    pub 类型表: &'请求 名号表,
    pub 锁定依赖: &'请求 [本机依赖],
    pub 工具链身份: &'请求 str,
    pub 平台身份: &'请求 str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct 本机源码产物 {
    pub 原文证据: Vec<u8>,
    pub 命令表证据: Vec<u8>,
    pub 常量表证据: Vec<u8>,
    pub 类型表证据: Vec<u8>,
    pub 锁定依赖: Vec<本机依赖>,
    pub 工具链身份: String,
    pub 平台身份: String,
    pub 执行源码: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum 本机生成错误 {
    来源缺失,
    语言形状(形状错误),
    语言语义(语义错误),
    当前子集不支持 { 节点: u32 },
    表达式不完整 { 节点: u32 },
    整数超界 { 节点: u32 },
    依赖不匹配,
}
