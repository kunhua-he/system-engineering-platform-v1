use v1_contract::错误码信息;
pub mod 能力号 {
    pub const 连接模型: u32 = 2501;
    pub const 提交生成任务: u32 = 2502;
    pub const 读取生成任务: u32 = 2503;
    pub const 取消生成任务: u32 = 2504;
    pub const 释放生成任务: u32 = 2505;
    pub const 释放句柄: u32 = 2506;
    pub const 资源快照: u32 = 2507;
    pub const 连接向量模型: u32 = 2508;
    pub const 生成嵌入: u32 = 2509;
    pub const 连接重排模型: u32 = 2510;
    pub const 执行重排: u32 = 2511;
}
pub mod 错误码 {
    pub const 参数不合法: u32 = 2501;
    pub const 协议不支持: u32 = 2502;
    pub const 句柄无效: u32 = 2503;
    pub const 任务无效: u32 = 2504;
    pub const 上游失败: u32 = 2505;
    pub const 资源受限: u32 = 2506;
    pub const 响应不合法: u32 = 2507;
}
pub const fn 码项(
    错误码: u32,
    名称: &'static [u8],
    描述: &'static [u8],
    可重试: u8,
    可自愈: u8,
    需人工: u8,
) -> 错误码信息 {
    错误码信息 {
        码值: 错误码,
        段位: 错误码 / 1000,
        名称: 名称.as_ptr(),
        说明: 描述.as_ptr(),
        可重试,
        可自愈,
        需人工,
        保留: 0,
    }
}

pub const 错误码信息表: [错误码信息; 7] = [
    码项(错误码::参数不合法, "参数不合法\0".as_bytes(), "连接参数、消息列表、文本列表或重排参数不符合契约\0".as_bytes(), 0, 0, 0),
    码项(错误码::协议不支持, "协议不支持\0".as_bytes(), "对话只支持 chat_completions、向量只支持 embeddings、重排只支持 rerank，其余协议明确拒绝\0".as_bytes(), 0, 0, 0),
    码项(错误码::句柄无效, "句柄无效\0".as_bytes(), "句柄不存在或已释放\0".as_bytes(), 0, 0, 0),
    码项(错误码::任务无效, "任务无效\0".as_bytes(), "生成任务不存在或已释放\0".as_bytes(), 0, 0, 0),
    码项(错误码::上游失败, "上游失败\0".as_bytes(), "模型端点返回错误状态或连接失败\0".as_bytes(), 1, 0, 0),
    码项(错误码::资源受限, "资源受限\0".as_bytes(), "句柄、任务、正文或条目数超过本扩展上限\0".as_bytes(), 0, 0, 1),
    码项(错误码::响应不合法, "响应不合法\0".as_bytes(), "上游响应不是可解析的流式事件或向量/重排结构\0".as_bytes(), 1, 0, 0),
];
pub const fn 错误码信息表段() -> v1_contract::表段<错误码信息> {
    v1_contract::表段::构造(错误码信息表.as_ptr(), 7)
}
