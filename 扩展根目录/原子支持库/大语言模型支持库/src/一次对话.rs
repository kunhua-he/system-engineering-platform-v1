//! 一次对话（2519）：把「复用或拉起 → 等就绪 → 申请许可 → 连接 → 提交 → 取结果 → 清理」
//! 串成**一个**能力。
//!
//! 为什么要有它：调用方（尤其网页）只该发一个请求。原来这条链要打二十次底座请求
//! （2512/2514×N/2516/2501/2502/2503×N/2517/2505/2506/2513），而且每一步的参数形状
//! 都要调用方自己拼 —— 那不是「一个能力」，是把底座内部结构摊给外面看。
//!
//! **短等待设计**：全平台单项超时 1000 毫秒（`契约声明/常量表.json`），所以这里不等到底。
//! 在 `等待毫秒` 内完成就直接回内容；没完成就回任务句柄，调用方再用 2503 取。
//! 这样一次请求能覆盖大多数情况，又不会因为超预算被判 `4 超时` 把结果丢掉。

use std::time::{Duration, Instant};

use serde_json::{json, Value};

use crate::编号与码面::错误码;
use crate::{连接与句柄, 推理许可, 生成任务, 模型服务};

/// 推理引擎与启动参数也一起兜底 —— 「一眼就会用」意味着连这个都不用记。
const 推理引擎: &str = "/opt/homebrew/bin/llama-server";
const 启动参数: &str = "-m {模型文件} --host 127.0.0.1 --port {端口} -c 4096 --no-webui";
const 一次等待上限毫秒: u64 = 110000;

/// 各类型的默认模型：调用方不传 `模型引用` 时用这个。
///
/// 底座面向本地私有部署，模型就放在固定位置；让每个调用方抄一遍绝对路径，
/// 抄错一个字母就等推理时才炸。要换模型显式传 `模型引用` 即可。
fn 默认模型(模型类型: &str) -> Option<&'static str> {
    match 模型类型 {
        "LLM文本模型" => Some("/Users/hekunhua/Documents/AI模型/文本模型/Qwen3-8B-Q4_K_M.gguf"),
        "VLM看图模型" => {
            Some("/Users/hekunhua/Documents/AI模型/图片分析模型/Qwen3VL-8B-Instruct-Q4_K_M.gguf")
        }
        "EM向量模型" => {
            Some("/Users/hekunhua/Documents/AI模型/Embedding模型/Qwen3-Embedding-8B-Q8_0.gguf")
        }
        "Rerank重排模型" => Some("/Users/hekunhua/Documents/AI模型/排序模型/Qwen3-Reranker-4B.Q8_0.gguf"),
        _ => None,
    }
}

pub(crate) struct 请求<'a> {
    pub(crate) 消息列表: &'a Value,
    pub(crate) 系统提示词: &'a str,
    pub(crate) 温度: f64,
    pub(crate) 最大令牌数: u64,
    pub(crate) 模型类型: &'a str,
    pub(crate) 模型引用: &'a str,
    pub(crate) 等待毫秒: u64,
}

/// 没做完时的统一回执：带上服务句柄（让调用方知道复用谁）与任务句柄（有的话）。
fn 未完成(服务句柄: u64, 任务句柄: Option<u64>, 状态: &str, 说明: &str) -> Value {
    json!({
        "已完成": false,
        "状态": 状态,
        "服务句柄": 服务句柄,
        "任务句柄": 任务句柄,
        "内容": "",
        "说明": 说明,
    })
}

pub(crate) fn 一次对话(请求: 请求<'_>) -> Result<Value, u32> {
    let 截止 = Instant::now() + Duration::from_millis(请求.等待毫秒.min(一次等待上限毫秒));
    let 模型类型: &'static str = 模型服务::规整模型类型(请求.模型类型)?;
    let 引用文本 = if 请求.模型引用.trim().is_empty() {
        默认模型(模型类型).ok_or(错误码::参数不合法)?
    } else {
        请求.模型引用.trim()
    };
    let 引用 = 模型服务::解析模型引用(引用文本)?;
    let 完整路径 = 引用.文件路径.clone().unwrap_or_default();

    // ① 有就复用，没有才拉起。不复用的话每轮对话都新起一个进程，几轮就爆内存。
    let (服务句柄, 端口) = match 模型服务::找已载入(&完整路径) {
        Some(已有) => 已有,
        None => {
            let 句柄 = 模型服务::拉起(
                &引用.标识,
                引用.文件路径.as_deref(),
                推理引擎,
                启动参数,
                0,
                "",
                模型类型,
                900,
                30,
            )?;
            let 剩余 = 截止.saturating_duration_since(Instant::now()).as_millis() as u64;
            if 剩余 == 0 || !模型服务::等待就绪(句柄, 剩余)? {
                return Ok(未完成(
                    句柄,
                    None,
                    "载入中",
                    "服务已拉起，模型正在载入。再发一次同样的请求就会拿到答案",
                ));
            }
            let 状态 = 模型服务::取状态(句柄)?;
            let 端口 = 状态
                .get("监听端口")
                .and_then(Value::as_u64)
                .ok_or(错误码::拉起失败)? as u16;
            (句柄, 端口)
        }
    };

    // ② 许可：同模型内排队，不同模型并行。
    let 许可 = 推理许可::申请(服务句柄, 3_000, 5_000)?;
    let 结果 = 跑一次生成(服务句柄, 端口, &引用.标识, &请求, 截止);
    // 不管成功失败都要还许可，否则租约到期前这个模型对别人是锁住的。
    let _ = 推理许可::归还(许可);
    结果
}

fn 跑一次生成(
    服务句柄: u64,
    端口: u16,
    模型名: &str,
    请求: &请求<'_>,
    截止: Instant,
) -> Result<Value, u32> {
    let 连接 = 连接与句柄::连接对话模型(
        模型名,
        &format!("http://127.0.0.1:{端口}"),
        "",
        "chat_completions",
        Vec::new(),
    )?;

    // 空列表 = 不带工具、不要结构化格式、不加额外头。
    let 空列表 = Value::Array(Vec::new());
    let 空对象 = Value::Object(serde_json::Map::new());
    let 提交结果 = 生成任务::提交(
        连接,
        生成任务::生成请求 {
            消息列表: 请求.消息列表,
            系统提示词: 请求.系统提示词,
            温度: 请求.温度,
            最大令牌数: 请求.最大令牌数,
            工具: &空列表,
            响应格式: &空对象,
            附加请求头: &空对象,
        },
    );

    let 任务句柄 = match 提交结果 {
        Ok(句柄) => 句柄,
        Err(码) => {
            let _ = 连接与句柄::释放(连接);
            return Err(码);
        }
    };

    // ③ 短等：在预算内拿到就回内容，拿不到就交任务句柄出去。
    loop {
        let 读数 = 生成任务::读取(任务句柄)?;
        let 已完成 = 读数.get("已完成").and_then(Value::as_bool).unwrap_or(false)
            && !读数.get("资源在途").and_then(Value::as_bool).unwrap_or(true);
        if 已完成 {
            let 内容 = 读数.get("内容").cloned().unwrap_or_else(|| json!(""));
            let 错误信息 = 读数
                .get("错误信息")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_owned();
            let _ = 生成任务::释放(任务句柄);
            let _ = 连接与句柄::释放(连接);
            if !错误信息.is_empty() {
                return Err(错误码::上游失败);
            }
            return Ok(json!({
                "已完成": true,
                "状态": "已完成",
                "服务句柄": 服务句柄,
                "任务句柄": 0,
                "内容": 内容,
            }));
        }
        if Instant::now() >= 截止 {
            // 不释放任务与连接：要留给调用方继续用 2503 取结果。
            return Ok(未完成(
                服务句柄,
                Some(任务句柄),
                "生成中",
                "还没生成完，用 2503 拿任务句柄取结果；或稍后重发同一个请求",
            ));
        }
        std::thread::sleep(Duration::from_millis(50));
    }
}
