//! 案例形状与读盘 —— 案例库的**唯一事实源是磁盘上的案例目录**，不是本文件里的任何表。
//!
//! # 案例目录形状（`测试验证/案例/形状.md` 是权威，这里只实现它）
//!
//! ```text
//! 测试验证/案例/<案例名>/
//!   案例.json        做什么：装载哪份声明 · 步骤链（能力编号 + 按契约行序的实参来源）
//!   输入.程序文本     真程序文本（我们的原生格式）。「程序」类案例必有；容器类案例没有
//!   期望.json        期望什么：按步骤一一对应（运行结果 或 诊断）
//! ```
//!
//! 编码一律 UTF-8，换行一律 LF。**`输入.程序文本` 不在这里转码**：它的字节原样送进能力，
//! 转码是调用方的事，案例库不该替调用方做决定。
//!
//! # 期望是**封闭枚举**，不是断言语言
//!
//! 判据只有下面 [`期望`] 与 [`产物判据`] 里那几个变体：没有变量、没有表达式、没有运算符、
//! 不能组合。加一种判据 = 加一个变体 = 改这一份实现；**加不出「写一条新断言」这回事**。

use std::path::{Path, PathBuf};

use crate::最小JSON::{self, 值};

/// 案例目录里放真程序文本的那一个文件名（**名字写死在一处**）。
pub const 程序文本文件名: &str = "输入.程序文本";

/// 实参的取值来源。**封闭枚举**。
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum 实参来源 {
    /// 案例目录里的 `输入.程序文本`。
    程序文本,
    /// 一个文件：相对路径按案例目录解，绝对路径原样用（只读语料走这条）。
    文件(PathBuf),
    /// 就地写的十六进制字节（小输入用，避免为几个字节建一个文件）。
    十六进制(Vec<u8>),
    /// 上一步的返回字节集（步骤链；`1105 → 1104` 的往返就走它）。
    上一步返回,
}

/// 一个实参：类型标签 + 来源。**行序即契约**，由 `案例.json` 里 `实参` 数组的排列给出。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 实参 {
    pub 类型标签: u32,
    pub 来源: 实参来源,
}

/// 一步：调一个能力编号。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 步骤 {
    pub 名: String,
    pub 能力编号: u32,
    pub 实参: Vec<实参>,
}

/// 成功时看返回槽的哪一件事。**封闭枚举**。
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum 产物判据 {
    /// 返回槽是空槽（`槽标志::空`）。
    空槽,
    /// 返回的字节集**逐字节等于**这个文件的字节。相对路径按案例目录解。
    逐字节等于文件(PathBuf),
    /// 返回的是字节集且长度 > 0。
    非空字节集,
    /// 只看转发成功，不看返回槽内容（读侧一类的调用）。
    不判,
}

/// 失败时期望的错误码。三项业务判断**必须写在案例里**——它们猜不出来（`README.md` 第七节）。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 错误码期望 {
    pub 码: u32,
    pub 名称: String,
    pub 可重试: bool,
    pub 可自愈: bool,
    pub 需人工: bool,
}

/// 一步的期望。
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum 期望 {
    /// 期望转发成功。
    成功 { 产物: 产物判据 },
    /// 期望**结构化失败**：死在哪一层 + 哪个错误码（+ 可选的返回槽判据）。
    /// **没有「跳过」这一档。**
    失败 {
        死在哪一层: String,
        错误码: 错误码期望,
        /// 失败时返回槽该是什么样。`不判` = 不看。宪法第 6 条「未命中返回空」
        /// 就靠这里写 `空槽` 来证 —— 不写就没人证它。
        产物: 产物判据,
    },
}

/// 一个案例。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 案例 {
    pub 名: String,
    pub 目录: PathBuf,
    pub 说明: String,
    /// 步骤链。**至少一步**——空步骤链是空集，不许算通过。
    pub 步骤: Vec<步骤>,
    /// 与 `步骤` 等长，一一对应。
    pub 期望: Vec<期望>,
}

impl 案例 {
    pub fn 程序文本路(&self) -> PathBuf {
        self.目录.join(程序文本文件名)
    }
}

/// 案例库里不是案例的目录（**写死一处**）：跑案例的程序自己住在这里。
const 非案例目录: &[&str] = &["跑案例"];

/// 读一个案例根下的全部案例，按目录名排序（顺序确定 ⇒ 回执可比）。
///
/// **fail-closed**：除 [`非案例目录`] 外，任何一个子目录缺 `案例.json` 或 `期望.json`
/// 都是**工具错误**（不是「跳过这个案例」）——静默跳过就是假绿。
pub fn 读全部(案例根: &Path) -> Result<Vec<案例>, String> {
    let 项 = std::fs::read_dir(案例根).map_err(|错| format!("读不到案例根 {}：{错}", 案例根.display()))?;
    let mut 名表: Vec<String> = Vec::new();
    for 一 in 项 {
        let 一 = 一.map_err(|错| format!("列案例根失败：{错}"))?;
        let 路 = 一.path();
        if !路.is_dir() {
            continue;
        }
        let 名 = 一.file_name().to_string_lossy().into_owned();
        if !非案例目录.contains(&名.as_str()) {
            名表.push(名);
        }
    }
    名表.sort();
    if 名表.is_empty() {
        return Err(format!(
            "案例根 {} 下 0 个案例目录 —— 空集不算通过（判据的可信性.md 第二节）",
            案例根.display()
        ));
    }
    let mut 出 = Vec::new();
    for 名 in 名表 {
        出.push(读一个(&案例根.join(&名))?);
    }
    Ok(出)
}

fn 读一个(目录: &Path) -> Result<案例, String> {
    let 清单 = 读JSON(&目录.join("案例.json"))?;
    let 名 = 要串(&清单, "案例名")?.to_owned();
    let 说明 = 要串(&清单, "说明")?.to_owned();
    let 步骤 = 读步骤(&清单, 目录)?;
    let 期望 = 读期望(&目录.join("期望.json"), 步骤.len(), 目录)?;
    if 步骤.is_empty() {
        return Err(format!("{}：步骤是空集 —— 空集不算通过", 目录.display()));
    }
    Ok(案例 { 名, 目录: 目录.to_path_buf(), 说明, 步骤, 期望 })
}

fn 读步骤(清单: &值, 目录: &Path) -> Result<Vec<步骤>, String> {
    let 表 = 清单
        .取("步骤")
        .and_then(|一| 一.表())
        .ok_or_else(|| format!("{}：`步骤` 缺失或不是数组", 目录.display()))?;
    let mut 出 = Vec::new();
    for (序, 一) in 表.iter().enumerate() {
        let 名 = 一
            .取("名")
            .and_then(|一| 一.串())
            .ok_or_else(|| format!("{}：步骤[{序}] 缺 `名`", 目录.display()))?
            .to_owned();
        let 能力编号 = 一
            .取("能力编号")
            .and_then(|一| 一.整数())
            .and_then(|数| u32::try_from(数).ok())
            .ok_or_else(|| format!("{}：步骤[{序}] 的 `能力编号` 缺失或不是 32 位整数", 目录.display()))?;
        let 实参表 = 一
            .取("实参")
            .and_then(|一| 一.表())
            .ok_or_else(|| format!("{}：步骤[{序}] 的 `实参` 缺失或不是数组", 目录.display()))?;
        let mut 实参 = Vec::new();
        for (位, 参) in 实参表.iter().enumerate() {
            let 类型标签 = 参
                .取("类型标签")
                .and_then(|一| 一.整数())
                .and_then(|数| u32::try_from(数).ok())
                .ok_or_else(|| {
                    format!("{}：步骤[{序}].实参[{位}] 的 `类型标签` 缺失或不是 32 位整数", 目录.display())
                })?;
            let 来源名 = 参
                .取("来源")
                .and_then(|一| 一.串())
                .ok_or_else(|| format!("{}：步骤[{序}].实参[{位}] 缺 `来源`", 目录.display()))?;
            let 值项 = 参.取("值");
            let 来源 = match 来源名 {
                "程序文本" => 实参来源::程序文本,
                "文件" => 实参来源::文件(PathBuf::from(
                    值项
                        .and_then(|一| 一.串())
                        .ok_or_else(|| {
                            format!("{}：步骤[{序}].实参[{位}] 来源是 `文件`，缺 `值`（路径）", 目录.display())
                        })?
                        .to_owned(),
                )),
                "十六进制" => {
                    let 文 = 值项.and_then(|一| 一.串()).ok_or_else(|| {
                        format!("{}：步骤[{序}].实参[{位}] 来源是 `十六进制`，缺 `值`", 目录.display())
                    })?;
                    实参来源::十六进制(解十六进制(文).map_err(|错| {
                        format!("{}：步骤[{序}].实参[{位}] 的十六进制：{错}", 目录.display())
                    })?)
                }
                "上一步返回" => 实参来源::上一步返回,
                其 => {
                    return Err(format!(
                        "{}：步骤[{序}].实参[{位}] 的 `来源` 不认：`{其}`（只认 程序文本 / 文件 / 十六进制 / 上一步返回）",
                        目录.display()
                    ));
                }
            };
            实参.push(实参 { 类型标签, 来源 });
        }
        出.push(步骤 { 名, 能力编号, 实参 });
    }
    Ok(出)
}

fn 读期望(路: &Path, 步骤数: usize, 目录: &Path) -> Result<Vec<期望>, String> {
    let 根 = 读JSON(路)?;
    let 表 = 根
        .取("步骤")
        .and_then(|一| 一.表())
        .ok_or_else(|| format!("{}：`步骤` 缺失或不是数组", 路.display()))?;
    if 表.len() != 步骤数 {
        return Err(format!(
            "{}：期望有 {} 条、步骤有 {步骤数} 条 —— 必须一一对应（不等就是案例自己写坏了）",
            路.display(),
            表.len()
        ));
    }
    let mut 出 = Vec::new();
    for (序, 一) in 表.iter().enumerate() {
        let 结果 = 一
            .取("结果")
            .and_then(|一| 一.串())
            .ok_or_else(|| format!("{}：步骤[{序}] 缺 `结果`", 路.display()))?;
        let 定 = match 结果 {
            "成功" => 期望::成功 { 产物: 读产物(一, 目录)? },
            "失败" => {
                let 层 = 一
                    .取("死在哪一层")
                    .and_then(|一| 一.串())
                    .ok_or_else(|| format!("{}：步骤[{序}] 结果=失败，必须有 `死在哪一层`", 路.display()))?
                    .to_owned();
                let 码项 = 一
                    .取("错误码")
                    .ok_or_else(|| format!("{}：步骤[{序}] 结果=失败，必须有 `错误码`", 路.display()))?;
                let 错误码 = 错误码期望 {
                    码: 要整数(码项, "码", 路)?,
                    名称: 要串(码项, "名称")?.to_owned(),
                    可重试: 要真假(码项, "可重试")?,
                    可自愈: 要真假(码项, "可自愈")?,
                    需人工: 要真假(码项, "需人工")?,
                };
                期望::失败 { 死在哪一层: 层, 错误码, 产物: 读产物(一, 目录)? }
            }
            其 => {
                return Err(format!(
                    "{}：步骤[{序}] 的 `结果` 不认：`{其}`（只认 成功 / 失败 —— 没有「跳过」这一档）",
                    路.display()
                ));
            }
        };
        出.push(定);
    }
    Ok(出)
}

fn 读产物(一: &值, 目录: &Path) -> Result<产物判据, String> {
    let Some(产物) = 一.取("产物") else {
        return Ok(产物判据::不判);
    };
    let 判 = 产物
        .取("判据")
        .and_then(|一| 一.串())
        .ok_or_else(|| format!("{}：`产物` 缺 `判据`", 目录.display()))?;
    match 判 {
        "空槽" => Ok(产物判据::空槽),
        "非空字节集" => Ok(产物判据::非空字节集),
        "不判" => Ok(产物判据::不判),
        "逐字节等于文件" => Ok(产物判据::逐字节等于文件(PathBuf::from(
            产物
                .取("文件")
                .and_then(|一| 一.串())
                .ok_or_else(|| "`逐字节等于文件` 缺 `文件`".to_owned())?
                .to_owned(),
        ))),
        其 => Err(format!("`产物.判据` 不认：`{其}`")),
    }
}

/// 相对路径按案例目录解；绝对路径原样用（只读语料在仓外）。
pub fn 解路(目录: &Path, 路: &Path) -> PathBuf {
    if 路.is_absolute() {
        路.to_path_buf()
    } else {
        目录.join(路)
    }
}

pub fn 解十六进制(文: &str) -> Result<Vec<u8>, String> {
    let 净: Vec<u8> = 文.bytes().filter(|字| !matches!(字, b' ' | b'\n' | b'\r' | b'\t')).collect();
    if !净.len().is_multiple_of(2) {
        return Err(format!("十六进制位数是奇数（{}）", 净.len()));
    }
    let mut 出 = Vec::with_capacity(净.len() / 2);
    for 对 in 净.chunks(2) {
        let 文 = std::str::from_utf8(对).map_err(|_| "不是 ASCII".to_owned())?;
        let 数 = u8::from_str_radix(文, 16).map_err(|_| format!("`{文}` 不是十六进制字节"))?;
        出.push(数);
    }
    Ok(出)
}

fn 读JSON(路: &Path) -> Result<值, String> {
    let 文 = std::fs::read_to_string(路).map_err(|错| format!("读不到 {}：{错}", 路.display()))?;
    最小JSON::解析(&文).map_err(|错| format!("{} 不是合法 JSON：{错}", 路.display()))
}

fn 要串<'a>(项: &'a 值, 键: &str) -> Result<&'a str, String> {
    项.取(键).and_then(|一| 一.串()).ok_or_else(|| format!("缺 `{键}`（或不是字符串）"))
}

fn 要整数(项: &值, 键: &str, 路: &Path) -> Result<u32, String> {
    项.取(键)
        .and_then(|一| 一.整数())
        .and_then(|数| u32::try_from(数).ok())
        .ok_or_else(|| format!("{}：`{键}` 缺失或不是 32 位整数", 路.display()))
}

fn 要真假(项: &值, 键: &str) -> Result<bool, String> {
    项.取(键).and_then(|一| 一.真假()).ok_or_else(|| format!("缺 `{键}`（或不是 true/false）"))
}

#[cfg(test)]
mod 测试 {
    use super::*;

    #[test]
    fn 十六进制按空白分组也解得对() {
        assert_eq!(解十六进制("4e 4f 54").unwrap(), b"NOT");
        assert_eq!(解十六进制("0a0b").unwrap(), vec![0x0a, 0x0b]);
        assert!(解十六进制("4e4").is_err(), "奇数位该被拒");
        assert!(解十六进制("zz").is_err(), "非十六进制该被拒");
    }

    #[test]
    fn 相对路按案例目录解_绝对路原样() {
        assert_eq!(解路(Path::new("/甲/乙"), Path::new("丙.txt")), PathBuf::from("/甲/乙/丙.txt"));
        assert_eq!(解路(Path::new("/甲/乙"), Path::new("/丙/丁")), PathBuf::from("/丙/丁"));
    }

    /// 反向样本：不认的 `来源` 必须报错，不许静默当成某个默认值。
    #[test]
    fn 不认的来源报错() {
        let 清单 = 最小JSON::解析(r#"{"步骤":[{"名":"甲","能力编号":1,"实参":[{"类型标签":4,"来源":"猜"}]}]}"#).unwrap();
        assert!(读步骤(&清单, Path::new("/甲")).is_err());
    }
}
