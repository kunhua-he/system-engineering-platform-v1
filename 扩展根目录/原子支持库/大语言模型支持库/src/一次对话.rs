//! 一次对话（2519）：把「复用或拉起 → 等就绪 → 申请许可 → 连接 → 提交 → 取结果 → 清理」
//! 串成**一个**能力。
//!
//! 为什么要有它：调用方（尤其网页）只该发一个请求。原来这条链要打二十次底座请求
//! （2512/2514×N/2516/2501/2502/2503×N/2517/2505/2506/2513），而且每一步的参数形状
//! 都要调用方自身拼 —— 那不是「一个能力」，是把底座内部结构摊给外面看。
//!
//! **短等待设计**：全平台单项超时 1000 毫秒（`契约声明/常量表.json`），所以这里不等到底。
//! 在 `等待毫秒` 内完成就直接回内容；没完成就回任务句柄，调用方再用 2503 取。
//! 这样一次请求能覆盖大多数情况，又不会因为超预算被判 `4 超时` 把结果丢掉。

use std::time::{Duration, Instant};

use serde_json::{Value, json};

use crate::编号与码面::错误码;
use crate::{模型服务, 生成任务, 连接与句柄};

/// 推理引擎与启动参数也一起兜底 —— 「一眼就会用」意味着连这个都不用记。
const 推理引擎: &str = "/opt/homebrew/bin/llama-server";
/// 推理引擎的启动参数。看图模型必须另带视觉投影层（`--mmproj`），
/// 少了它上游不认图片，报出来只是一句「上游失败」，看不出是缺投影层。
const 基础启动参数: &str = "-m {模型文件} --host 127.0.0.1 --port {端口} -c 8192 --no-webui";

/// 按模型类型出启动参数。投影层不写死路径：同目录里按模型名推，
/// 规则是「去掉量化后缀、前面加 mmproj-、后面加 -F16.gguf」
/// （`Qwen3VL-8B-Instruct-Q4_K_M.gguf` → `mmproj-Qwen3VL-8B-Instruct-F16.gguf`）。
fn 启动参数(模型类型: &str, 模型文件: &str) -> String {
    if 模型类型 != "VLM看图模型" {
        return 基础启动参数.to_owned();
    }
    match 推投影层(模型文件) {
        Some(投影) => format!("{基础启动参数} --mmproj {投影}"),
        None => 基础启动参数.to_owned(),
    }
}

fn 推投影层(模型文件: &str) -> Option<String> {
    let 路径 = std::path::Path::new(模型文件);
    let 目录 = 路径.parent()?;
    let 文件名 = 路径.file_stem()?.to_str()?;
    // 去掉 -Q4_K_M / .Q8_0 这类量化尾巴
    let mut 基名 = 文件名;
    for 标记 in [
        "-Q4_K_M", "-Q5_K_M", "-Q8_0", "-Q4_0", ".Q8_0", ".Q4_K_M", "-F16", "-BF16",
    ] {
        if let Some(位) = 基名.find(标记) {
            基名 = &基名[..位];
        }
    }
    let 候选 = 目录.join(format!("mmproj-{基名}-F16.gguf"));
    if 候选.exists() {
        Some(候选.to_string_lossy().into_owned())
    } else {
        None
    }
}
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
        "Rerank重排模型" => {
            Some("/Users/hekunhua/Documents/AI模型/排序模型/Qwen3-Reranker-4B.Q8_0.gguf")
        }
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

/// 反复问「就绪了吗」直到过了截止时间。
///
/// 为什么不能只问一次：`2515` 单次等待封顶 800 毫秒（全平台单项超时 120 秒要留传回时间），
/// 而真实载入本机模型要 1–3 秒，一轮必然回假 —— 那会让每次冷启动都白跑一趟。
fn 循环等就绪(句柄: u64, 截止: Instant) -> Result<(), u32> {
    loop {
        let 剩余 = 截止.saturating_duration_since(Instant::now()).as_millis() as u64;
        if 剩余 == 0 {
            return Ok(());
        }
        if 模型服务::等待就绪(句柄, 剩余)? {
            return Ok(());
        }
    }
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
            let 句柄 = 模型服务::拉起(模型服务::模型启动参数 {
                模型短名: &引用.标识,
                模型文件: 引用.文件路径.as_deref(),
                可执行文件: 推理引擎,
                启动参数: &启动参数(模型类型, 引用.文件路径.as_deref().unwrap_or("")),
                监听端口: 0,
                就绪路径: "",
                模型类型,
                闲置超时秒: 900,
                载入超时秒: 30,
            })?;
            // 2515 单次等待封顶 800 毫秒（全平台单项超时要留传回时间），
            // 一轮根本盖不住真实载入（本机模型 1–3 秒），必须循环到截止。
            循环等就绪(句柄, 截止)?;
            let 状态 = 模型服务::取状态(句柄)?;
            if 状态.get("状态").and_then(Value::as_str) != Some("已载入") {
                return Ok(未完成(
                    句柄,
                    None,
                    "载入中",
                    "服务已拉起，模型正在载入。再发一次同样的请求就会拿到答案",
                ));
            }
            let 端口 = 状态
                .get("监听端口")
                .and_then(Value::as_u64)
                .ok_or(错误码::拉起失败)? as u16;
            (句柄, 端口)
        }
    };

    // 许可由真实生成任务取得并持有；HTTP 短等返回不能归还在途许可。
    跑一次生成(服务句柄, 端口, &引用.标识, &请求, 截止)
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

    // 生成线程已经复制连接配置，不让内部连接随短等待返回后遗留。
    let _ = 连接与句柄::释放(连接);
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
            && !读数
                .get("资源在途")
                .and_then(Value::as_bool)
                .unwrap_or(true);
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
