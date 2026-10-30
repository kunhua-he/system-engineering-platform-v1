use crate::编号与码面::错误码;
use crate::时刻解析::{拆时刻与正文, 校验时刻};

const 日志上限字节: usize = 8388608;
const 命中上限行: usize = 50000;

pub fn 执行时间窗筛选(
    日志文本: &str,
    起始时刻: &str,
    结束时刻: &str,
    前缀长度: usize,
) -> Result<String, u32> {
    if !校验时刻(起始时刻) || !校验时刻(结束时刻) {
        return Err(错误码::文本参数不合法);
    }
    if 结束时刻 < 起始时刻 {
        return Err(错误码::文本参数不合法);
    }
    if !(10..=32).contains(&前缀长度) {
        return Err(错误码::文本参数不合法);
    }
    if 日志文本.len() > 日志上限字节 {
        return Err(错误码::文本资源受限);
    }
    let mut 命中表: Vec<serde_json::Value> = Vec::new();
    let mut 无法解析行数: usize = 0;
    let mut 已截断 = false;
    for (序号, 原行) in 日志文本.lines().enumerate() {
        let Some((时刻串, 正文)) = 拆时刻与正文(原行, 前缀长度) else {
            无法解析行数 += 1;
            continue;
        };
        if 时刻串.as_str() < 起始时刻 || 时刻串.as_str() > 结束时刻 {
            continue;
        }
        if 命中表.len() >= 命中上限行 {
            已截断 = true;
            break;
        }
        命中表.push(serde_json::json!({
            "行号": 序号 + 1,
            "时刻": 时刻串,
            "正文": 正文,
        }));
    }
    let 载荷 = serde_json::json!({
        "命中数": 命中表.len(),
        "窗口": [起始时刻, 结束时刻],
        "命中行": 命中表,
        "无法解析行数": 无法解析行数,
        "截断": 已截断,
    });
    serde_json::to_string(&载荷).map_err(|_| 错误码::文本内容不合法)
}
