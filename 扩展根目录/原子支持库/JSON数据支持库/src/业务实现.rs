//! JSON 数据支持库业务总入口：**只做入口上界校验与按能力号分派**，实现按关注点住同名字文件夹
//! `src/业务实现/`（`开发规范.md` 第六节「改一处不必读全件」）。
//!
//! | 件 | 职责 | 能力号 |
//! | --- | --- | --- |
//! | 本文件 | 解析入口上界与深度校验 · 5218–5220 转接响应塑形 · 主分派 | 5201–5220 总口 |
//! | `指针与列表.rs` | JSON 指针寻址 · 列表取值 · 真/假文本判定 | 5202 · 5203 · 5205 · 5206 · 5208 · 5209 · 5210 |
//! | `查找与排序.rs` | 单项命中判定 · 类型序比较 · 标量文本化 | 5205 · 5206 · 5208 · 5213 |
//! | `展平.rs` | 点分路径拼接 · 字典展平递归 · 结构条目展平递归 | 5211 · 5212 |
//! | `格式互转与合并.rs` | CSV 全文解析 · JSON 深合并 · JSON 到 YAML 值转换 | 5214 · 5215 · 5217 |
//!
//! 解析入口 `解析文本上限` 留在本文件：`响应塑形实现` 按件直接引用，改动面最小。

use crate::编号与码面::{能力号, 错误码};
use v1_contract::复合值载荷::{复合值, 复合元素, 编码复合值载荷};

#[path = "业务实现/指针与列表.rs"]
mod 指针与列表;
#[path = "业务实现/查找与排序.rs"]
mod 查找与排序;
#[path = "业务实现/展平.rs"]
mod 展平;
#[path = "业务实现/格式互转与合并.rs"]
mod 格式互转与合并;

use 查找与排序::{取比较键, 单项命中, 比较值, 标量文本};
use 展平::{展平上下文, 展平条目递归, 展平字典递归};
use 指针与列表::{取列表, 取逻辑文本, 指针取值};
use 格式互转与合并::{深合并值, 转YAML值, 解析CSV全文};

pub(crate) fn 解析文本上限(原文: &str, 上限: usize) -> Result<serde_json::Value, u32> {
    if 原文.len() > 上限 {
        return Err(错误码::JSON资源受限);
    }
    let (mut 深度, mut 字符串内, mut 转义中) = (0usize, false, false);
    for 字节值 in 原文.bytes() {
        if 字符串内 {
            if 转义中 {
                转义中 = false;
            } else if 字节值 == b'\\' {
                转义中 = true;
            } else if 字节值 == b'"' {
                字符串内 = false;
            }
        } else {
            match 字节值 {
                b'"' => 字符串内 = true,
                b'[' | b'{' => {
                    深度 += 1;
                    if 深度 > 64 {
                        return Err(错误码::JSON资源受限);
                    }
                }
                b']' | b'}' => 深度 = 深度.saturating_sub(1),
                _ => {}
            }
        }
    }
    crate::JSON树解析::解析JSON树(原文).map_err(|_| 错误码::JSON参数不合法)
}
fn 解析文本(原文: &str) -> Result<serde_json::Value, u32> {
    解析文本上限(原文, 65536)
}

pub fn 执行文本操作(编号: u32, 文本参数表: &[&str]) -> Result<(u32, Vec<u8>), u32> {
    if 编号 == 能力号::裁剪响应 {
        return crate::响应塑形实现::执行裁剪响应(文本参数表);
    }
    if 编号 == 能力号::压缩描述字段 {
        return crate::响应塑形实现::执行压缩描述字段(文本参数表);
    }
    if 编号 == 能力号::提取带前缀JSON {
        return crate::响应塑形实现::执行提取带前缀JSON(文本参数表);
    }
    if 编号 == 能力号::反序列化CSV {
        if 文本参数表[1].chars().count() != 1 {
            return Err(错误码::JSON参数不合法);
        }
        let 分隔符字符 = 文本参数表[1].chars().next().ok_or(错误码::JSON参数不合法)?;
        if matches!(分隔符字符, '"' | '\r' | '\n') {
            return Err(错误码::JSON参数不合法);
        }
        if 文本参数表[0].len() > 65536 {
            return Err(错误码::JSON资源受限);
        }
        let 严格模式 = 取逻辑文本(文本参数表[2])?;
        let 行表 = 解析CSV全文(文本参数表[0], 分隔符字符, 严格模式)?;
        let 行值表: Vec<serde_json::Value> = 行表
            .into_iter()
            .map(|行条目| serde_json::Value::Array(行条目.into_iter().map(serde_json::Value::String).collect()))
            .collect();
        return Ok((4, serde_json::Value::Array(行值表).to_string().into_bytes()));
    }
    if 编号 == 能力号::深合并 {
        let mut 基础值 = 解析文本(文本参数表[0])?;
        let 覆盖值 = 解析文本(文本参数表[1])?;
        深合并值(&mut 基础值, &覆盖值);
        return Ok((4, 基础值.to_string().into_bytes()));
    }
    if 编号 == 能力号::解析YAML {
        if 文本参数表[0].len() > 65536 {
            return Err(错误码::JSON资源受限);
        }
        let 解析值: serde_json::Value =
            serde_yaml_ng::from_str(文本参数表[0]).map_err(|_| 错误码::JSON参数不合法)?;
        return Ok((4, 解析值.to_string().into_bytes()));
    }
    if 编号 == 能力号::序列化YAML {
        if 文本参数表[0].len() > 65536 {
            return Err(错误码::JSON资源受限);
        }
        let 解析值 = 解析文本(文本参数表[0])?;
        let YAML文本 = serde_yaml_ng::to_string(&转YAML值(&解析值)).map_err(|_| 错误码::JSON参数不合法)?;
        if YAML文本.len() > 65536 {
            return Err(错误码::JSON资源受限);
        }
        return Ok((4, YAML文本.into_bytes()));
    }
    let 解析值 = 解析文本(文本参数表[0])?;
    if 编号 == 能力号::提取摘要 {
        let (类型名称, 成员数量) = match &解析值 {
            serde_json::Value::Null => ("空值", 0),
            serde_json::Value::Bool(_) => ("逻辑", 0),
            serde_json::Value::Number(_) => ("数值", 0),
            serde_json::Value::String(_) => ("文本", 0),
            serde_json::Value::Array(列表值) => ("列表", 列表值.len()),
            serde_json::Value::Object(成员表) => ("对象", 成员表.len()),
        };
        let 元素表 = vec![
            复合元素 {
                名称: "类型名称".into(),
                值: 复合值::文本载荷(类型名称.into()),
            },
            复合元素 {
                名称: "成员数量".into(),
                值: 复合值::整数值(成员数量 as i64),
            },
            复合元素 {
                名称: "规范文本".into(),
                值: 复合值::文本载荷(解析值.to_string()),
            },
        ];
        return Ok((
            103,
            编码复合值载荷(103, &元素表).map_err(|_| 错误码::JSON资源受限)?,
        ));
    }
    let 返回文本 = match 编号 {
        能力号::规范化JSON => 解析值.to_string(),
        能力号::按指针取值 => 指针取值(&解析值, 文本参数表[1])?.to_string(),
        能力号::按指针取文本 => 指针取值(&解析值, 文本参数表[1])?
            .as_str()
            .ok_or(错误码::JSON类型不符)?
            .to_owned(),
        能力号::按字段查找 => {
            let 列表值 = 取列表(文本参数表[0])?;
            let 期望值 = 解析文本(文本参数表[2])?;
            let 直接匹配 = 取逻辑文本(文本参数表[3])?;
            match 列表值.iter().find(|条目| 单项命中(条目, 文本参数表[1], 直接匹配, &期望值)) {
                Some(命中项) => 命中项.to_string(),
                None => String::new(),
            }
        }
        能力号::过滤 => {
            let 列表值 = 取列表(文本参数表[0])?;
            let 期望值 = 解析文本(文本参数表[2])?;
            let 直接匹配 = 取逻辑文本(文本参数表[3])?;
            let 命中表: Vec<serde_json::Value> = 列表值
                .into_iter()
                .filter(|条目| 单项命中(条目, 文本参数表[1], 直接匹配, &期望值))
                .collect();
            serde_json::Value::Array(命中表).to_string()
        }
        能力号::映射转换 => {
            let 列表值 = 取列表(文本参数表[0])?;
            let 映射对象 = match 解析文本(文本参数表[1])? {
                serde_json::Value::Object(字段映射) => 字段映射,
                _ => return Err(错误码::JSON类型不符),
            };
            let mut 结果表 = Vec::with_capacity(列表值.len());
            for 条目 in 列表值 {
                match 条目 {
                    serde_json::Value::Object(原对象) => {
                        let mut 新对象 = serde_json::Map::new();
                        for (字段名, 字段值) in 原对象 {
                            let 新字段名 = 映射对象
                                .get(&字段名)
                                .and_then(|映射值| 映射值.as_str())
                                .map(str::to_owned)
                                .unwrap_or_else(|| 字段名.clone());
                            新对象.insert(新字段名, 字段值);
                        }
                        结果表.push(serde_json::Value::Object(新对象));
                    }
                    其他值 => 结果表.push(其他值),
                }
            }
            serde_json::Value::Array(结果表).to_string()
        }
        能力号::按字段排序 => {
            let mut 列表值 = 取列表(文本参数表[0])?;
            let 升序 = 取逻辑文本(文本参数表[2])?;
            let 直接匹配 = 取逻辑文本(文本参数表[3])?;
            let 字段名 = 文本参数表[1];
            列表值.sort_by(|左项, 右项| {
                比较值(取比较键(左项, 字段名, 直接匹配), 取比较键(右项, 字段名, 直接匹配))
            });
            if !升序 {
                列表值.reverse();
            }
            serde_json::Value::Array(列表值).to_string()
        }
        能力号::列表添加 => {
            let mut 列表值 = 取列表(文本参数表[0])?;
            if 列表值.len() >= 10000 {
                return Err(错误码::JSON资源受限);
            }
            列表值.push(解析文本(文本参数表[1])?);
            serde_json::Value::Array(列表值).to_string()
        }
        能力号::列表移除 => {
            let mut 列表值 = 取列表(文本参数表[0])?;
            let 目标值 = 解析文本(文本参数表[1])?;
            if let Some(命中位置) = 列表值.iter().position(|条目| 条目 == &目标值) {
                列表值.remove(命中位置);
            }
            serde_json::Value::Array(列表值).to_string()
        }
        能力号::展平字典 => {
            let 数据值 = 解析文本(文本参数表[0])?;
            let 分隔符 = 文本参数表[1];
            let 保留扁平键 = 取逻辑文本(文本参数表[2])?;
            let 最大深度: usize = 文本参数表[3]
                .trim()
                .parse()
                .map_err(|_| 错误码::JSON参数不合法)?;
            if 最大深度 == 0 || 最大深度 > 64 {
                return Err(错误码::JSON参数不合法);
            }
            let mut 收录 = serde_json::Map::new();
            match &数据值 {
                serde_json::Value::Object(成员表) => {
                    for (字段名, 字段值) in 成员表 {
                        let 是标量 = !字段值.is_object();
                        if 是标量 && !保留扁平键 {
                            continue;
                        }
                        展平字典递归(字段值, 字段名, 分隔符, 最大深度, &mut 收录);
                    }
                }
                其他值 => {
                    if 保留扁平键 {
                        收录.insert(String::new(), 其他值.clone());
                    }
                }
            }
            serde_json::Value::Object(收录).to_string()
        }
        能力号::展平结构条目 => {
            let 数据值 = 解析文本(文本参数表[0])?;
            let 最大深度: usize = 文本参数表[3]
                .trim()
                .parse()
                .map_err(|_| 错误码::JSON参数不合法)?;
            let 最大条目数: usize = 文本参数表[4]
                .trim()
                .parse()
                .map_err(|_| 错误码::JSON参数不合法)?;
            if 最大深度 == 0 || 最大深度 > 64 || 最大条目数 == 0 || 最大条目数 > 100_000 {
                return Err(错误码::JSON参数不合法);
            }
            let mut 上下文 = 展平上下文 {
                分隔符: 文本参数表[1],
                索引格式: 文本参数表[2],
                超深标记: 文本参数表[5],
                根路径: 文本参数表[6],
                最大条目数,
                条目表: Vec::new(),
                已截断: false,
            };
            展平条目递归(&数据值, "", 最大深度, &mut 上下文);
            serde_json::json!({
                "条目列表": 上下文.条目表,
                "总条目数": 上下文.条目表.len(),
                "已截断": 上下文.已截断,
            })
            .to_string()
        }
        能力号::规范化条目指纹 => {
            let 条目表 = 取列表(文本参数表[0])?;
            let 字段顺序: Vec<String> = match 解析文本(文本参数表[1])? {
                serde_json::Value::Array(字段值表) => 字段值表
                    .iter()
                    .map(|字段值| 字段值.as_str().unwrap_or_default().to_owned())
                    .collect(),
                _ => return Err(错误码::JSON类型不符),
            };
            if 字段顺序.is_empty() || 字段顺序.len() > 64 {
                return Err(错误码::JSON参数不合法);
            }
            let 条目分隔符 = 文本参数表[2];
            let 字段分隔符 = 文本参数表[3];
            let mut 行表: Vec<String> = Vec::with_capacity(条目表.len());
            for 条目项 in &条目表 {
                let mut 字段表: Vec<String> = Vec::with_capacity(字段顺序.len());
                for 字段名 in &字段顺序 {
                    let 字段值 = 条目项.get(字段名).unwrap_or(&serde_json::Value::Null);
                    字段表.push(标量文本(字段值));
                }
                行表.push(字段表.join(字段分隔符));
            }
            let 规范化文本 = 行表.join(条目分隔符);
            if 规范化文本.len() > 65536 {
                return Err(错误码::JSON资源受限);
            }
            use sha2 as 摘要算法;
            use sha2::Digest as 摘要接口;
            let mut 摘要器 = 摘要算法::Sha256::new();
            摘要接口::update(&mut 摘要器, 规范化文本.as_bytes());
            let 十六进制 = 摘要接口::finalize(摘要器)
                .iter()
                .map(|字节| format!("{字节:02x}"))
                .collect::<String>();
            serde_json::json!({ "指纹": 十六进制 }).to_string()
        }
        _ => return Err(错误码::JSON参数不合法),
    };
    if 返回文本.len() > 65536 {
        return Err(错误码::JSON资源受限);
    }
    Ok((4, 返回文本.into_bytes()))
}

#[cfg(test)]
mod 验证样本 {
    use super::*;
    #[test]
    fn 保留引擎私有同名对象键() {
        let 原文 = r#"{"$serde_json::private::Number":"123"}"#;
        assert_eq!(执行文本操作(5201, &[原文]).unwrap().1, 原文.as_bytes());
    }
    #[test]
    fn 大数空值和路径不混淆() {
        let 原文 = r#"{"金额":123456789012345678901234567890,"空":null,"假":false,"零":0,"空文":"","a/b":{"~":"中文\u0000"}}"#;
        for (路径, 期望) in [
            ("/金额", "123456789012345678901234567890"),
            ("/空", "null"),
            ("/假", "false"),
            ("/零", "0"),
            ("/空文", "\"\""),
        ] {
            assert_eq!(
                执行文本操作(5202, &[原文, 路径]).unwrap().1,
                期望.as_bytes()
            );
        }
        assert_eq!(
            执行文本操作(5203, &[原文, "/a~1b/~0"]).unwrap().1,
            "中文\0".as_bytes()
        );
        assert_eq!(执行文本操作(5202, &[原文, "/不存在"]), Err(5202));
        assert_eq!(执行文本操作(5203, &[原文, "/零"]), Err(5203));
        assert_eq!(执行文本操作(5202, &[原文, "/~2"]), Err(5201));
        assert_eq!(执行文本操作(5201, &["NaN"]), Err(5201));
        assert_eq!(
            执行文本操作(5201, &[&("[".repeat(65) + &"]".repeat(65))]),
            Err(5204)
        );
    }
}
