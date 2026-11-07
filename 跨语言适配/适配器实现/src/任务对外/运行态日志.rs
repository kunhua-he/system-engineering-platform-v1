//! 可靠当前态日志、持久意图与排他所有权。
use std::collections::BTreeMap;
use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::path::PathBuf;
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use v1_dispatch::{调用任务阶段, 调用节点阶段};

/// 落盘文件名（在运行数据根的 `数据库` 子目录下）。
const 文件名: &str = "调用任务运行态.jsonl";

/// 压实触发线：日志涨到这么多字节，启动时按当前态重写一遍。
///
/// 数字依据（实测，当前制品）：一条记录约 152 字节，一个「提交 + 释放」的任务约 761 字节，
/// 4 MiB ≈ 5500 个任务的历史。50,000 行（7.6 MB）折叠只要 13 毫秒（同缓存热度下
/// 0.542 秒 vs 空日志 0.529 秒）⇒ **压实不是为了启动快，是为了磁盘不无限长**。
const 压实字节阈值: u64 = 4 * 1024 * 1024;

/// 一行记录。字段名就是线上名，读回来的人不用对着代码猜。
#[derive(Debug, Clone, Serialize, Deserialize)]
struct 落盘行 {
    #[serde(default)]
    日志版本: u32,
    任务标识: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    请求标识: Option<String>,
    #[serde(default)]
    摘要: u64,
    /// 释放标记：真删一条记录也写一行（日志只追加），读回时按它把任务与判重键一起抹掉。
    #[serde(default)]
    释放: bool,
    /// 快照头：压实后唯一的一行「账本头」，只承载**最大号**。
    ///
    /// 为什么必须有它：最大号是从各行任务标识里折出来的；压实会把全部已释放任务的行丢掉，
    /// 一旦活跃任务清空就没有任何行记得「发到过几号」，重启后发号会回头撞历史号。
    #[serde(default)]
    快照头: bool,
    /// 只对快照头有意义：压实前的最大任务标识。
    #[serde(default)]
    最大号: u64,
    阶段: String,
    节点: BTreeMap<String, String>,
}

/// 从日志恢复出来的一条任务（**没有调度实例**：进程重启后实例本就没了）。
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct 恢复任务 {
    pub 阶段: 调用任务阶段,
    /// 按节点标识字典序；顺序只影响回执里节点表的排列，不影响判定。
    pub 节点: BTreeMap<String, 调用节点阶段>,
    pub 请求标识: Option<String>,
    pub 摘要: u64,
    pub 意图可靠: bool,
}

/// 重启快照：读完全部日志折叠出来的现状。
#[derive(Debug, Default, Clone)]
pub(crate) struct 重启快照 {
    pub 任务: BTreeMap<u64, 恢复任务>,
    /// 判重键 → (任务标识, 摘要)。
    pub 幂等: BTreeMap<String, (u64, u64)>,
    /// 用过的最大任务标识（发号从这里接着走，避免与历史号相撞）。
    pub 最大号: u64,
    pub 故障: Option<String>,
}

impl 重启快照 {
    /// 把一行折进快照（同标识后写覆盖前写；幂等键跟着最新那条走）。
    fn 折(&mut self, 行: 落盘行) -> Result<(), String> {
        if 行.日志版本 > 1 { return Err("运行态日志版本未知".to_owned()); }
        if 行.快照头 {
            // 压实后的账本头只答一件事：发号发到过哪。没有它，压掉全部任务后发号会回头。
            self.最大号 = self.最大号.max(行.最大号);
            return Ok(());
        }
        self.最大号 = self.最大号.max(行.任务标识);
        if 行.释放 {
            self.任务.remove(&行.任务标识);
            self.幂等.retain(|_, 凭据| 凭据.0 != 行.任务标识);
            return Ok(());
        }
        let 阶段 = 由名(行.阶段.as_str()).ok_or_else(|| format!("未知任务阶段：{}", 行.阶段))?;
        let 节点 = 行
            .节点
            .iter()
            .map(|(标识, 名)| 节点由名(名.as_str()).map(|阶段| (标识.clone(), 阶段)).ok_or_else(|| format!("未知节点阶段：{名}")))
            .collect::<Result<BTreeMap<String, 调用节点阶段>, String>>()?;
        self.最大号 = self.最大号.max(行.任务标识);
        if let Some(键) = &行.请求标识 {
            self.幂等.insert(键.clone(), (行.任务标识, 行.摘要));
        }
        self.任务.insert(
            行.任务标识,
            恢复任务 {
                阶段,
                节点,
                请求标识: 行.请求标识,
                摘要: 行.摘要,
                意图可靠: 行.日志版本 == 1,
            },
        );
        Ok(())
    }

    /// 重启对账：**只放确认过的东西进状态机**。
    ///
    /// - 落盘时正在执行（`执行中` / `收尾中`）⇒ 记 **未知**：执行体随进程消失，
    ///   没有任何一方回报过它做没做成。写成「失败」是替能力宣布结局 —— 那是猜。
    /// - 版本 1 的未启动状态有可靠意图先行约束，故可取消；
    ///   旧版本没有该证据，未启动快照仍恢复未知，不能倒推从未执行。
    /// - 已经是终态的一个都不动（不翻历史）。
    ///
    /// 任务阶段跟着走：有未知 ⇒ 未确认；一个未知都没有（全部未开始）⇒ 已取消。
    pub(crate) fn 对账(&mut self) {
        for 任务条 in self.任务.values_mut() {
            if !matches!(
                任务条.阶段,
                调用任务阶段::排队中 | 调用任务阶段::执行中 | 调用任务阶段::收尾中
            ) {
                continue;
            }
            let mut 有未知 = false;
            for 节点阶段 in 任务条.节点.values_mut() {
                if matches!(*节点阶段, 调用节点阶段::执行中 | 调用节点阶段::收尾中)
                {
                    *节点阶段 = 调用节点阶段::未知;
                    有未知 = true;
                } else if matches!(
                    *节点阶段,
                    调用节点阶段::等待依赖 | 调用节点阶段::就绪 | 调用节点阶段::等资源
                ) {
                    if 任务条.意图可靠 {
                        *节点阶段 = 调用节点阶段::已取消;
                    } else {
                        *节点阶段 = 调用节点阶段::未知;
                        有未知 = true;
                    }
                }
            }
            let 有失败 = 任务条
                .节点
                .values()
                .any(|阶段| *阶段 == 调用节点阶段::失败);
            let 全成功 = !任务条.节点.is_empty()
                && 任务条.节点.values().all(|阶段| *阶段 == 调用节点阶段::成功);
            任务条.阶段 = if 有未知 {
                调用任务阶段::未确认
            } else if 有失败 {
                调用任务阶段::失败
            } else if 全成功 {
                调用任务阶段::成功
            } else {
                调用任务阶段::已取消
            };
        }
    }
}

/// 写者文件的唯一所有者：先解锁再关描述符，覆盖构造失败及最终析构。
#[derive(Debug)]
struct 独占写者 { 锁文件: File }
impl 独占写者 {
    fn 取得(锁文件: File) -> std::io::Result<Self> {
        锁文件.try_lock().map_err(std::io::Error::other)?;
        Ok(Self { 锁文件 })
    }
}
impl std::ops::Deref for 独占写者 {
    type Target = File;
    fn deref(&self) -> &Self::Target { &self.锁文件 }
}
impl Drop for 独占写者 {
    fn drop(&mut self) {
        if let Err(错误) = self.锁文件.unlock() { eprintln!("持久写者显式解锁失败：{错误}"); }
    }
}

/// 持有终身排他文件锁；错误粘存，故障后不再受理新工作。
#[derive(Debug)]
pub(crate) struct 任务落盘 {
    路径: PathBuf,
    写锁: Mutex<Option<String>>,
    所有权: Option<独占写者>,
    #[cfg(test)]
    冲刷故障: std::sync::atomic::AtomicBool,
}

impl 任务落盘 {
    pub(crate) fn 打开() -> Result<Self, String> {
        let 根 = v1_dataroot::解析当前环境().map_err(|错误| format!("{错误:?}"))?;
        let 目录 = v1_dataroot::确保子目录(&根, v1_dataroot::子目录::数据库).map_err(|错误| format!("{错误:?}"))?;
        let 落盘 = Self::由路径(目录.join(文件名));
        落盘.检查()?;
        // 超阈值就按当前态重写一遍。压实失败**不阻止启动**：日志本身仍可用，只是磁盘继续长；
        // 故障照实报到 stderr，不静默吞掉。
        if 落盘.需要压实()
            && let Err(错误) = 落盘.压实()
        {
            eprintln!("运行态日志压实失败（继续使用原日志）：{错误}");
        }
        Ok(落盘)
    }

    /// 是否已到压实线。**只按字节**判：行数与字节线性相关，多一条判据就多一处漂移。
    pub(crate) fn 需要压实(&self) -> bool {
        std::fs::metadata(&self.路径)
            .map(|元| 元.len() >= 压实字节阈值)
            .unwrap_or(false)
    }

    /// 按**当前态**原子压实：一行账本头（最大号）+ 每个活任务最新一态。
    ///
    /// 保留什么：最大号（发号不许回头）、仍在表里的任务（**含未确认凭据**）、它们的判重键。
    /// 丢什么：已被后写覆盖的历史行、已释放任务的行 —— 释放时判重键已经抹掉，丢掉不会复活。
    ///
    /// 安全边界：先写同目录临时件并 `sync_all`，再 `rename` 替换，最后同步父目录。
    /// 中途任何一步失败，原日志不受影响 —— 绝不出现半份日志。
    pub(crate) fn 压实(&self) -> Result<bool, String> {
        self.检查()?;
        let 快照 = self.读回()?;
        let 头 = 落盘行 {
            日志版本: 1, 任务标识: 0, 请求标识: None, 摘要: 0, 释放: false,
            快照头: true, 最大号: 快照.最大号, 阶段: String::new(), 节点: BTreeMap::new(),
        };
        let mut 缓冲 = serde_json::to_vec(&头).map_err(|错误| format!("压实编码失败：{错误}"))?;
        缓冲.push(b'\n');
        for (标识, 条) in &快照.任务 {
            let 行 = 落盘行 {
                日志版本: 1, 任务标识: *标识, 请求标识: 条.请求标识.clone(), 摘要: 条.摘要,
                释放: false, 快照头: false, 最大号: 0, 阶段: 条.阶段.名().to_owned(),
                节点: 条.节点.iter().map(|(名, 阶段)| (名.clone(), 阶段.名().to_owned())).collect(),
            };
            缓冲.extend_from_slice(
                &serde_json::to_vec(&行).map_err(|错误| format!("压实编码失败：{错误}"))?,
            );
            缓冲.push(b'\n');
        }
        let 临时 = self.路径.with_extension("压实");
        {
            let mut 件 = OpenOptions::new()
                .create(true)
                .truncate(true)
                .write(true)
                .open(&临时)
                .map_err(|错误| format!("压实临时件打不开：{错误}"))?;
            件.write_all(&缓冲).map_err(|错误| format!("压实写入失败：{错误}"))?;
            件.sync_all().map_err(|错误| format!("压实同步失败：{错误}"))?;
        }
        std::fs::rename(&临时, &self.路径).map_err(|错误| format!("压实替换失败：{错误}"))?;
        if let Some(父路径目录) = self.路径.parent() {
            File::open(父路径目录)
                .and_then(|件| 件.sync_all())
                .map_err(|错误| format!("压实父目录同步失败：{错误}"))?;
        }
        Ok(true)
    }

    fn 由路径(路径: PathBuf) -> Self {
        let 锁路径 = 路径.with_extension("lock");
        let 所有权 = (|| -> std::io::Result<独占写者> {
            let 文件句柄 = OpenOptions::new().create(true).truncate(false).read(true).write(true).open(锁路径)?;
            let 所有权 = 独占写者::取得(文件句柄)?;
            let 日志件 = OpenOptions::new().create(true).append(true).open(&路径)?;
            日志件.sync_data()?;
            if let Some(父路径目录) = 路径.parent() { File::open(父路径目录)?.sync_all()?; }
            Ok(所有权)
        })();
        match 所有权 {
            Ok(所有权) => Self { 路径, 所有权: Some(所有权), 写锁: Mutex::new(None), #[cfg(test)] 冲刷故障: std::sync::atomic::AtomicBool::new(false) },
            Err(错误) => Self { 路径, 所有权: None, 写锁: Mutex::new(Some(format!("存储打开或独占失败：{错误}"))), #[cfg(test)] 冲刷故障: std::sync::atomic::AtomicBool::new(false) },
        }
    }

    #[cfg(test)]
    pub(crate) fn 指定路径(路径: PathBuf) -> Self { Self::由路径(路径) }

    pub(crate) fn 检查(&self) -> Result<(), String> {
        let 故障 = self.写锁.lock().unwrap_or_else(|中毒| 中毒.into_inner());
        if let Some(错误) = 故障.as_ref() { return Err(错误.clone()); }
        if self.所有权.is_none() { return Err("存储无独占所有权".to_owned()); }
        Ok(())
    }

    fn 冲刷文件(&self, 件: &File) -> std::io::Result<()> {
        #[cfg(test)]
        if self.冲刷故障.swap(false, std::sync::atomic::Ordering::SeqCst) {
            return Err(std::io::Error::other("定向注入冲刷故障"));
        }
        件.sync_data()
    }

    fn 写行(&self, 行: 落盘行) -> Result<(), String> {
        let mut 故障 = self.写锁.lock().unwrap_or_else(|中毒| 中毒.into_inner());
        if let Some(错误) = 故障.as_ref() { return Err(错误.clone()); }
        let 写入结果 = (|| -> Result<(), String> {
            let mut 文本 = serde_json::to_vec(&行).map_err(|错误| format!("日志编码失败：{错误}"))?;
            文本.push(b'\n');
            let mut 件 = OpenOptions::new().append(true).open(&self.路径).map_err(|错误| format!("日志打开失败：{错误}"))?;
            件.write_all(&文本).map_err(|错误| format!("日志写入失败：{错误}"))?;
            self.冲刷文件(&件).map_err(|错误| format!("日志冲刷失败：{错误}"))
        })();
        if let Err(错误) = &写入结果 { *故障 = Some(错误.clone()); }
        写入结果
    }

    pub(crate) fn 追加(&self, 任务标识: u64, 请求标识: Option<&str>, 摘要: u64,
        阶段: 调用任务阶段, 节点: &BTreeMap<String, 调用节点阶段>) -> Result<(), String> {
        self.写行(落盘行 {
            日志版本: 1, 任务标识, 请求标识: 请求标识.map(str::to_owned), 摘要, 释放: false,
            快照头: false, 最大号: 0,
            阶段: 阶段.名().to_owned(),
            节点: 节点.iter().map(|(标识, 阶段)| (标识.clone(), 阶段.名().to_owned())).collect(),
        })
    }

    pub(crate) fn 追加释放(&self, 任务标识: u64, 请求标识: Option<&str>) -> Result<(), String> {
        self.写行(落盘行 { 日志版本: 1, 任务标识, 请求标识: 请求标识.map(str::to_owned),
            摘要: 0, 释放: true, 快照头: false, 最大号: 0, 阶段: String::new(), 节点: BTreeMap::new() })
    }

    pub(crate) fn 读回(&self) -> Result<重启快照, String> {
        self.检查()?;
        let mut 文本 = String::new();
        File::open(&self.路径).and_then(|mut 件| 件.read_to_string(&mut 文本)).map_err(|错误| format!("日志读取失败：{错误}"))?;
        if !文本.is_empty() && !文本.ends_with('\n') { return Err("日志尾行不完整".to_owned()); }
        let mut 快照 = 重启快照::default();
        for 行 in 文本.lines() {
            let 解 = serde_json::from_str::<落盘行>(行).map_err(|错误| format!("日志损坏：{错误}"))?;
            快照.折(解)?;
        }
        Ok(快照)
    }
}

/// 阶段名严格解析，未知名称由恢复口明确拒绝。
fn 由名(名: &str) -> Option<调用任务阶段> {
    调用任务阶段::全部.iter().copied().find(|项| 项.名() == 名)
}

/// 节点阶段名严格解析，不以业务失败替代存储损坏。
fn 节点由名(名: &str) -> Option<调用节点阶段> {
    调用节点阶段::全部
        .iter()
        .copied()
        .find(|项| 项.名() == 名)

}

/// 落盘注入：把任务存储的「每写一条」接到运行态日志上。
///
/// 请求标识与摘要**不在任务记录里**（记录只答「到哪一步了」），所以由提交侧随注入一起给。
pub(crate) struct 落盘注入 {
    落盘: std::sync::Arc<任务落盘>,
    请求标识: Option<String>,
    摘要: u64,
}

impl 落盘注入 {
    pub(crate) fn 新建(
        落盘: std::sync::Arc<任务落盘>,
        请求标识: Option<String>,
        摘要: u64,
    ) -> Self {
        Self {
            落盘,
            请求标识,
            摘要,
        }
    }
}

impl crate::调用任务装配::任务存储回调 for 落盘注入 {
    fn 写入(
        &mut self,
        记录: &crate::调用任务装配::任务记录,
    ) -> Result<(), crate::调用任务装配::存储错误> {
        let Ok(号) = 记录.任务标识.parse::<u64>() else {
            return Err(crate::调用任务装配::存储错误::持久故障("任务标识不是有效整数".to_owned()));
        };
        self.落盘.追加(
            号,
            self.请求标识.as_deref(),
            self.摘要,
            记录.阶段,
            &记录.节点阶段,
        ).map_err(crate::调用任务装配::存储错误::持久故障)
    }
}

#[cfg(test)]
mod 测试 {
    use super::*;

    fn 临时路径(名: &str) -> PathBuf {
        std::env::temp_dir().join(format!("运行态日志_{名}_{}.jsonl", std::process::id()))
    }

    fn 节点表(对: &[(&str, 调用节点阶段)]) -> BTreeMap<String, 调用节点阶段> {
        对.iter()
            .map(|(标识, 阶段)| ((*标识).to_owned(), *阶段))
            .collect()
    }

    /// 判据：后写覆盖前写；幂等键与最大号都从日志恢复得出来。
    #[test]
    fn 追加后读回取最后一条() {
        let 路径 = 临时路径("最后一条");
        let 日志 = 任务落盘::指定路径(路径.clone());
        日志.追加(
            3,
            Some("请求一"),
            77,
            调用任务阶段::执行中,
            &节点表(&[("节点一", 调用节点阶段::执行中)]),
        ).unwrap();
        日志.追加(
            3,
            Some("请求一"),
            77,
            调用任务阶段::成功,
            &节点表(&[("节点一", 调用节点阶段::成功)]),
        ).unwrap();
        let 快照 = 日志.读回().unwrap();
        assert_eq!(快照.最大号, 3);
        assert_eq!(
            快照.任务.get(&3).map(|条| 条.阶段),
            Some(调用任务阶段::成功),
            "同标识后写的必须覆盖前写的"
        );
        assert_eq!(快照.幂等.get("请求一"), Some(&(3, 77)));
        let _ = std::fs::remove_file(路径);
    }

    /// 判据：重启对账**只放确认过的进状态机** —— 在跑的判未知（不是失败），没开工的判已取消。
    #[test]
    fn 对账把在途判成未知与已取消() {
        let 路径 = 临时路径("对账");
        let 日志 = 任务落盘::指定路径(路径.clone());
        日志.追加(
            9,
            None,
            0,
            调用任务阶段::执行中,
            &节点表(&[
                ("跑着的", 调用节点阶段::执行中),
                ("等着没起的", 调用节点阶段::等待依赖),
                ("已经成功的", 调用节点阶段::成功),
            ]),
        ).unwrap();
        日志.追加(
            10,
            None,
            0,
            调用任务阶段::成功,
            &节点表(&[("完成的", 调用节点阶段::成功)]),
        ).unwrap();
        let mut 快照 = 日志.读回().unwrap();
        快照.对账();
        let 九 = 快照.任务.get(&9).expect("任务九必须在");
        assert_eq!(
            九.阶段,
            调用任务阶段::未确认,
            "在跑的一律判未确认：没有回报为证，说失败就是替能力宣布结局"
        );
        assert_eq!(
            九.节点.get("跑着的"),
            Some(&调用节点阶段::未知),
            "节点级也只能说未知，不许写失败"
        );
        assert_eq!(
            九.节点.get("等着没起的"),
            Some(&调用节点阶段::已取消),
            "没开工的节点判已取消"
        );
        assert_eq!(
            九.节点.get("已经成功的"),
            Some(&调用节点阶段::成功),
            "已终态的节点一个都不许动"
        );
        assert_eq!(
            快照.任务.get(&10).map(|条| 条.阶段),
            Some(调用任务阶段::成功),
            "历史终态任务不许被对账改动"
        );
        let _ = std::fs::remove_file(路径);
    }

    /// 判据：节点全部已确认成功 ⇒ 任务就是成功；有失败节点 ⇒ 失败。不许一律写已取消。
    #[test]
    fn 对账全节点成功收成成功() {
        let 路径 = 临时路径("对账全成功");
        let 日志 = 任务落盘::指定路径(路径.clone());
        日志
            .追加(
                11,
                None,
                0,
                调用任务阶段::执行中,
                &节点表(&[
                    ("示例入口节点", 调用节点阶段::成功),
                    ("示例出口节点", 调用节点阶段::成功),
                ]),
            )
            .unwrap();
        日志
            .追加(
                12,
                None,
                0,
                调用任务阶段::执行中,
                &节点表(&[
                    ("失败节点", 调用节点阶段::失败),
                    ("示例旁支节点", 调用节点阶段::成功),
                ]),
            )
            .unwrap();
        日志
            .追加(
                13,
                None,
                0,
                调用任务阶段::收尾中,
                &节点表(&[
                    ("取消节点", 调用节点阶段::已取消),
                    ("示例尾部节点", 调用节点阶段::成功),
                ]),
            )
            .unwrap();
        let mut 快照 = 日志.读回().unwrap();
        快照.对账();
        assert_eq!(
            快照.任务[&11].阶段,
            调用任务阶段::成功,
            "全节点成功就是成功，不许写成已取消"
        );
        assert_eq!(
            快照.任务[&12].阶段,
            调用任务阶段::失败,
            "有失败节点且无未知 ⇒ 失败"
        );
        assert_eq!(
            快照.任务[&13].阶段,
            调用任务阶段::已取消,
            "有取消节点且无未知 ⇒ 已取消"
        );
        let _ = std::fs::remove_file(路径);
    }

    #[test]
    fn 坏行拒绝且第二写者拒绝() {
        let 路径 = 临时路径("坏行拒绝");
        let 日志 = 任务落盘::指定路径(路径.clone());
        std::fs::write(&路径, "坏行\n").unwrap();
        assert!(日志.读回().is_err());
        assert!(任务落盘::指定路径(路径.clone()).检查().is_err());
        drop(日志);
        assert!(任务落盘::指定路径(路径.clone()).检查().is_ok());
        let _ = std::fs::remove_file(路径);
    }

    #[test]
    fn 旧等待快照恢复未知且墓碑准确删键() {
        let 路径 = 临时路径("旧快照");
        let 日志 = 任务落盘::指定路径(路径.clone());
        std::fs::write(&路径, "{\"任务标识\":5,\"请求标识\":\"旧请求\",\"阶段\":\"排队中\",\"节点\":{\"旧节点\":\"等待依赖\"}}\n").unwrap();
        let mut 快照 = 日志.读回().unwrap();
        快照.对账();
        assert_eq!(快照.任务[&5].阶段, 调用任务阶段::未确认);
        日志.追加释放(5, None).unwrap();
        assert!(日志.读回().unwrap().幂等.is_empty());
        let _ = std::fs::remove_file(路径);
    }

    #[test]
    fn 真实打开错误可见且不假成功() {
        let 日志 = 任务落盘::指定路径(临时路径("不存在目录").join("日志"));
        assert!(日志.追加释放(5, None).unwrap_err().contains("存储打开"));
    }
}

#[cfg(test)]
mod 排他反证 {
    use super::*;
    #[test]
    fn 最后所有者解锁不受继承描述符拖延() {
        let 路径 = std::env::temp_dir().join(format!("所有者解锁_{}.jsonl", std::process::id()));
        let 日志持有者 = std::sync::Arc::new(任务落盘::指定路径(路径.clone()));
        日志持有者.检查().unwrap();
        // 复制同一开放文件描述，与子进程继承占锁的内核语义一致；不依赖抢中时间窗口。
        let 继承描述符 = 日志持有者.所有权.as_ref().unwrap().try_clone().unwrap();
        let 共享持有者 = std::sync::Arc::clone(&日志持有者);
        drop(日志持有者);
        assert!(任务落盘::指定路径(路径.clone()).检查().is_err(), "仍有最终所有者时不得提前解锁");
        drop(共享持有者);
        let 接管持有者 = 任务落盘::指定路径(路径.clone());
        assert!(接管持有者.检查().is_ok(), "最终所有者退出须显式解锁，继承描述符仍开着也不可拖延");
        drop(接管持有者);
        drop(继承描述符);
        std::fs::remove_file(路径.with_extension("lock")).unwrap();
        std::fs::remove_file(路径).unwrap();
    }
    #[test]
    fn 子进程尝试同根写者() {
        let Some(路径) = std::env::var_os("V1_WRITER_PROBE") else { return; };
        assert!(任务落盘::指定路径(PathBuf::from(路径)).检查().is_err());
    }
    #[test]
    fn 两个进程不能同时持有写者() {
        let 路径 = std::env::temp_dir().join(format!("排他反证_{}.jsonl", std::process::id()));
        let 日志 = 任务落盘::指定路径(路径.clone());
        日志.检查().unwrap();
        let 子状态 = std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "任务对外::运行态日志::排他反证::子进程尝试同根写者", "--nocapture"])
            .env("V1_WRITER_PROBE", &路径).status().unwrap();
        assert!(子状态.success());
        drop(日志);
        任务落盘::指定路径(路径.clone()).检查().unwrap();
        let _ = std::fs::remove_file(路径);
    }
    #[test]
    fn 已开日志真实写入故障阻断后续准入() {
        let 路径 = std::env::temp_dir().join(format!("写入反证_{}.jsonl", std::process::id()));
        let 日志 = 任务落盘::指定路径(路径.clone());
        std::fs::remove_file(&路径).unwrap();
        std::fs::create_dir(&路径).unwrap();
        let 故障 = 日志.追加释放(7, None).unwrap_err();
        assert!(故障.contains("日志打开失败"));
        assert_eq!(日志.检查(), Err(故障));
        std::fs::remove_dir(路径).unwrap();
    }
}

#[cfg(test)]
mod 冲刷反证 {
    use super::*;

    fn 节点(对: &[(&str, 调用节点阶段)]) -> BTreeMap<String, 调用节点阶段> {
        对.iter()
            .map(|(标识, 阶段)| ((*标识).to_owned(), *阶段))
            .collect()
    }

    #[test]
    fn 未知枚举坏尾行与读失败均拒绝() {
        let 路径 = std::env::temp_dir().join(format!("严格恢复_{}.jsonl", std::process::id()));
        let 日志 = 任务落盘::指定路径(路径.clone());
        std::fs::write(&路径, "{\"任务标识\":9,\"阶段\":\"陌生阶段\",\"节点\":{}}\n").unwrap();
        assert!(日志.读回().unwrap_err().contains("未知任务阶段"));
        std::fs::write(&路径, "{\"任务标识\":9,\"阶段\":\"成功\",\"节点\":{\"节点\":\"陌生阶段\"}}\n").unwrap();
        assert!(日志.读回().unwrap_err().contains("未知节点阶段"));
        std::fs::write(&路径, "{}").unwrap();
        assert!(日志.读回().unwrap_err().contains("尾行不完整"));
        std::fs::remove_file(&路径).unwrap();
        assert!(日志.读回().unwrap_err().contains("日志读取失败"));
    }
    #[test]
    fn 冲刷错误注入传播且粘存() {
        let 路径 = std::env::temp_dir().join(format!("冲刷注入_{}.jsonl", std::process::id()));
        let 日志 = 任务落盘::指定路径(路径.clone());
        日志.冲刷故障.store(true, std::sync::atomic::Ordering::SeqCst);
        let 故障 = 日志.追加释放(11, None).unwrap_err();
        assert!(故障.contains("日志冲刷失败"));
        assert!(故障.contains("定向注入"));
        assert_eq!(日志.检查(), Err(故障));
        std::fs::remove_file(路径).unwrap();
    }

    #[test]
    fn 压实保留最大号活跃任务与判重且不复活已释放() {
        let 路径 = std::env::temp_dir().join(format!("压实_{}.jsonl", std::process::id()));
        let 日志 = 任务落盘::指定路径(路径.clone());
        日志.追加(1, Some("已释放请求"), 11, 调用任务阶段::成功,
            &节点(&[("压实入口节点", 调用节点阶段::成功)])).unwrap();
        日志.追加释放(1, Some("已释放请求")).unwrap();
        日志.追加(2, Some("活跃请求"), 22, 调用任务阶段::执行中,
            &节点(&[("压实出口节点", 调用节点阶段::执行中)])).unwrap();
        日志.追加(3, Some("未确认请求"), 33, 调用任务阶段::未确认,
            &节点(&[("压实未确认节点", 调用节点阶段::未知)])).unwrap();
        日志.追加(2, Some("活跃请求"), 22, 调用任务阶段::成功,
            &节点(&[("压实出口节点", 调用节点阶段::成功)])).unwrap();
        let 压前字节 = std::fs::metadata(&路径).unwrap().len();
        assert!(日志.压实().unwrap(), "压实必须真做一遍");
        let 快照 = 日志.读回().unwrap();
        assert_eq!(快照.最大号, 3, "最大号必须留下：压掉全部任务后发号也不许回头");
        assert!(!快照.任务.contains_key(&1), "已释放的任务压实后不许复活");
        assert!(!快照.幂等.contains_key("已释放请求"), "已释放任务的判重键不许复活");
        assert_eq!(快照.任务.get(&2).map(|条| 条.阶段), Some(调用任务阶段::成功),
            "活跃任务只留最新一态");
        assert_eq!(快照.幂等.get("活跃请求"), Some(&(2, 22)), "判重键跟着活跃任务保留");
        let 三 = 快照.任务.get(&3).expect("未确认任务必须原样保留");
        assert_eq!(三.阶段, 调用任务阶段::未确认);
        assert_eq!(三.节点.get("压实未确认节点"), Some(&调用节点阶段::未知), "未确认凭据不许被压实洗白");
        assert!(三.意图可靠, "版本 1 的可靠意图标记压实后必须还在");
        assert!(std::fs::metadata(&路径).unwrap().len() < 压前字节, "压实必须真变小");
        日志.追加(4, Some("压后请求"), 44, 调用任务阶段::执行中,
            &节点(&[("压实收尾节点", 调用节点阶段::执行中)])).unwrap();
        let 后 = 日志.读回().unwrap();
        assert_eq!(后.最大号, 4, "压实之后再追加，发号接着走");
        assert_eq!(后.任务.get(&4).map(|条| 条.阶段), Some(调用任务阶段::执行中));
        std::fs::remove_file(路径).unwrap();
    }
}
