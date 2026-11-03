//! 行列结构变更后同步子项图片坐标，避免图片跟错行列。
use serde_json::{Map, Value};

pub(super) fn 调整图片坐标(
    表格节点: &Value,
    坐标维度: usize,
    变更位置: usize,
    操作名称: &str,
    目标位置: usize,
) -> Value {
    let mut 图片映射 = Map::new();
    if let Some(原图映射) = 表格节点.get("__单元格图片").and_then(Value::as_object) {
        for (图片键名, 图片路径) in 原图映射 {
            let Some((行号文本, 列号文本)) = 图片键名.split_once(':') else {
                continue;
            };
            let (Ok(行序号), Ok(列序号)) = (行号文本.parse::<usize>(), 列号文本.parse::<usize>())
            else {
                continue;
            };
            let mut 图片坐标 = [行序号, 列序号];
            let 原始位置 = 图片坐标[坐标维度];
            let 新位置 = match 操作名称 {
                "插入" if 原始位置 >= 变更位置 => 原始位置 + 1,
                "删除" if 原始位置 == 变更位置 => continue,
                "删除" if 原始位置 > 变更位置 => 原始位置 - 1,
                "移动" if 原始位置 == 变更位置 => 目标位置,
                "移动"
                    if 变更位置 < 目标位置 && 原始位置 > 变更位置 && 原始位置 <= 目标位置 =>
                {
                    原始位置 - 1
                }
                "移动"
                    if 变更位置 > 目标位置 && 原始位置 >= 目标位置 && 原始位置 < 变更位置 =>
                {
                    原始位置 + 1
                }
                _ => 原始位置,
            };
            图片坐标[坐标维度] = 新位置;
            图片映射.insert(format!("{}:{}", 图片坐标[0], 图片坐标[1]), 图片路径.clone());
        }
    }
    Value::Object(图片映射)
}
