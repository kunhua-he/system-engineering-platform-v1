//! 任务对外 · 运行态日志 —— 任务状态落盘的**唯一入口**（追加式，不改写）。
//!
//! # 为什么是追加日志而不是库
//!
//! 平台侧没有 Rust SQLite 绑定，唯一的 SQL 通道是能力 5101/5102（每调用一条独立连接、
//! 参数要编组成槽）。而任务状态写在**热路径**上（节点每收口一次就变），走一次跨语言转发
//! 比写一行本地日志更慢也更脆。追加日志 + `fsync` 满足这里要的最小保证：
//! **单写者、只追加、崩溃后最多丢最后一条没 flush 的记录**，而重放是幂等的（同标识后写覆盖前写）。
//!
//! 这与方案单 `§3.9` 的「新开一张运行态库、只抄最小集」在**落点与范围**上一致
//! （新增运行态落盘、只存任务/节点当前状态 + 判重键，不进治理库、不做事件重放），
//! 差的只是载体：日志文件而不是 SQLite 表。理由记在这里，避免后来人以为漏做。
//!
//! # 一条记录是什么
//!
//! `任务标识 · 请求标识 · 摘要 · 任务阶段 · 全部节点阶段` —— 正好是内存里那份任务记录的形状
//! （`任务存储::任务记录` 加判重键）。**不记时刻、不记事件序列**：时刻是实例内的单调钟，
//! 跨进程没有意义；事件序列要重放语义，本平台明确不做。
//!
//! # 重启对账（不猜成功）
//!
//! 进程重启时库里可能留着「在跑」的状态，而跑它的进程已经没了。对账口径：
//! 任务阶段 `排队中 / 执行中 / 收尾中` ⇒ **失败**；节点 `执行中 / 收尾中` ⇒ **失败**；
//! 节点 `等待依赖 / 就绪 / 等资源` ⇒ **已取消**。绝不把「不知道死活」当成成功。

use std::collections::BTreeMap;
use std::fs::{File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use v1_dispatch::{调用任务阶段, 调用节点阶段};

/// 落盘文件名（在运行数据根的 `数据库` 子目录下）。
const 文件名: &str = "调用任务运行态.jsonl";

/// 一行记录。字段名就是线上名，读回来的人不用对着代码猜。
#[derive(Debug, Clone, Serialize, Deserialize)]
struct 落盘行 {
    任务标识: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    请求标识: Option<String>,
    #[serde(default)]
    摘要: u64,
    /// 释放标记：真删一条记录也写一行（日志只追加），读回时按它把任务与判重键一起抹掉。
    #[serde(default)]
    释放: bool,
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
}

/// 重启快照：读完全部日志折叠出来的现状。
#[derive(Debug, Default, Clone)]
pub(crate) struct 重启快照 {
    pub 任务: BTreeMap<u64, 恢复任务>,
    /// 判重键 → (任务标识, 摘要)。
    pub 幂等: BTreeMap<String, (u64, u64)>,
    /// 用过的最大任务标识（发号从这里接着走，避免与历史号相撞）。
    pub 最大号: u64,
}

impl 重启快照 {
    /// 把一行折进快照（同标识后写覆盖前写；幂等键跟着最新那条走）。
    fn 折(&mut self, 行: 落盘行) {
        self.最大号 = self.最大号.max(行.任务标识);
        if 行.释放 {
            // 释放 = 内存里真删掉：读回也要真删，连同判重键（否则重启后同标识被旧记录挡住）。
            self.任务.remove(&行.任务标识);
            if let Some(键) = &行.请求标识 {
                self.幂等.remove(键);
            }
            return;
        }
        let 阶段 = 由名(行.阶段.as_str()).unwrap_or(调用任务阶段::失败);
        let 节点 = 行
            .节点
            .iter()
            .map(|(标识, 名)| (标识.clone(), 节点由名(名.as_str())))
            .collect::<BTreeMap<String, 调用节点阶段>>();
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
            },
        );
    }

    /// 重启对账：把「在跑」的状态判成**失败·已中断**，未开始的节点判成**已取消**。
    ///
    /// 只对**落盘时仍在途**的那些生效；已经是终态的一个都不动（不翻历史）。
    pub(crate) fn 对账(&mut self) {
        for 条 in self.任务.values_mut() {
            if !matches!(
                条.阶段,
                调用任务阶段::排队中 | 调用任务阶段::执行中 | 调用任务阶段::收尾中
            ) {
                continue;
            }
            条.阶段 = 调用任务阶段::失败;
            for 节点阶段 in 条.节点.values_mut() {
                if matches!(*节点阶段, 调用节点阶段::执行中 | 调用节点阶段::收尾中)
                {
                    *节点阶段 = 调用节点阶段::失败;
                } else if matches!(
                    *节点阶段,
                    调用节点阶段::等待依赖 | 调用节点阶段::就绪 | 调用节点阶段::等资源
                ) {
                    *节点阶段 = 调用节点阶段::已取消;
                }
            }
        }
    }
}

/// 运行态日志句柄：一个进程一个（单写者）。
#[derive(Debug)]
pub(crate) struct 任务落盘 {
    路径: PathBuf,
    /// 追加是「写一行 + flush」；锁保证两行不交错（同一个 File 被多线程写时必须串行）。
    写锁: Mutex<()>,
}

impl 任务落盘 {
    /// 打开日志（**只有生产调用**：测试一律走 [`Self::指定路径`]，不碰真运行数据目录）。
    #[cfg_attr(test, allow(dead_code))]
    /// 解析运行数据根 → 建 `数据库` 子目录 → 只负责追加。
    ///
    /// **拿不到运行数据根就返回 `None`**：那说明这台机器上没配运行数据位置，
    /// 此时退化成纯内存语义（行为不退化），而不是把状态写到源码树里。
    pub(crate) fn 打开() -> Option<Self> {
        let 根 = v1_dataroot::解析当前环境().ok()?;
        let 目录 = v1_dataroot::确保子目录(&根, v1_dataroot::子目录::数据库).ok()?;
        Some(Self {
            路径: 目录.join(文件名),
            写锁: Mutex::new(()),
        })
    }

    /// 用指定路径开（判据用：不碰真运行数据目录）。
    #[cfg(test)]
    pub(crate) fn 指定路径(路径: PathBuf) -> Self {
        Self {
            路径,
            写锁: Mutex::new(()),
        }
    }

    /// 追加一条任务现状。**写失败不 panic**：落盘是旁路，不能让一次磁盘抖动掀翻在跑的图。
    pub(crate) fn 追加(
        &self,
        任务标识: u64,
        请求标识: Option<&str>,
        摘要: u64,
        阶段: 调用任务阶段,
        节点: &BTreeMap<String, 调用节点阶段>,
    ) {
        let 行 = 落盘行 {
            任务标识,
            请求标识: 请求标识.map(str::to_owned),
            摘要,
            释放: false,
            阶段: 阶段.名().to_owned(),
            节点: 节点
                .iter()
                .map(|(标识, 阶段)| (标识.clone(), 阶段.名().to_owned()))
                .collect(),
        };
        let Ok(文本) = serde_json::to_string(&行) else {
            return;
        };
        let _守卫 = self.写锁.lock().unwrap_or_else(|中毒| 中毒.into_inner());
        let Ok(mut 件) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.路径)
        else {
            return;
        };
        if 件.write_all(文本.as_bytes()).is_ok() && 件.write_all(b"\n").is_ok() {
            // 落盘才算数：不 fsync 的话，崩溃后「写过的」可能还在页缓存里。
            let _ = 件.sync_data();
        }
    }

    /// 追加一条**释放**记录（任务已从内存真删；落盘跟上，否则重启后又冒出来）。
    pub(crate) fn 追加释放(&self, 任务标识: u64, 请求标识: Option<&str>) {
        let 行 = 落盘行 {
            任务标识,
            请求标识: 请求标识.map(str::to_owned),
            摘要: 0,
            释放: true,
            阶段: String::new(),
            节点: BTreeMap::new(),
        };
        let Ok(文本) = serde_json::to_string(&行) else {
            return;
        };
        let _守卫 = self.写锁.lock().unwrap_or_else(|中毒| 中毒.into_inner());
        let Ok(mut 件) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.路径)
        else {
            return;
        };
        if 件.write_all(文本.as_bytes()).is_ok() && 件.write_all(b"\n").is_ok() {
            let _ = 件.sync_data();
        }
    }

    /// 读回全部记录并折叠成快照（坏行跳过：一行坏不许让整个任务表读不出来）。
    pub(crate) fn 读回(&self) -> 重启快照 {
        let mut 快照 = 重启快照::default();
        let Ok(件) = File::open(&self.路径) else {
            return 快照;
        };
        for 行 in BufReader::new(件).lines() {
            let Ok(文本) = 行 else { continue };
            if 文本.trim().is_empty() {
                continue;
            }
            if let Ok(解) = serde_json::from_str::<落盘行>(&文本) {
                快照.折(解);
            }
        }
        快照
    }
}

/// 阶段名 → 任务阶段（认不出按**失败**：宁可说它坏了，也不替它猜成成功）。
fn 由名(名: &str) -> Option<调用任务阶段> {
    调用任务阶段::全部.iter().copied().find(|项| 项.名() == 名)
}

/// 节点阶段名 → 节点阶段（认不出按**失败**，同上）。
fn 节点由名(名: &str) -> 调用节点阶段 {
    调用节点阶段::全部
        .iter()
        .copied()
        .find(|项| 项.名() == 名)
        .unwrap_or(调用节点阶段::失败)
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
            return Ok(());
        };
        self.落盘.追加(
            号,
            self.请求标识.as_deref(),
            self.摘要,
            记录.阶段,
            &记录.节点阶段,
        );
        Ok(())
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
        );
        日志.追加(
            3,
            Some("请求一"),
            77,
            调用任务阶段::成功,
            &节点表(&[("节点一", 调用节点阶段::成功)]),
        );
        let 快照 = 日志.读回();
        assert_eq!(快照.最大号, 3);
        assert_eq!(
            快照.任务.get(&3).map(|条| 条.阶段),
            Some(调用任务阶段::成功),
            "同标识后写的必须覆盖前写的"
        );
        assert_eq!(快照.幂等.get("请求一"), Some(&(3, 77)));
        let _ = std::fs::remove_file(路径);
    }

    /// 判据：重启对账把在途判成失败/已取消，不猜成功。
    #[test]
    fn 对账把在途判成失败与已取消() {
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
        );
        日志.追加(
            10,
            None,
            0,
            调用任务阶段::成功,
            &节点表(&[("完成的", 调用节点阶段::成功)]),
        );
        let mut 快照 = 日志.读回();
        快照.对账();
        let 九 = 快照.任务.get(&9).expect("任务九必须在");
        assert_eq!(九.阶段, 调用任务阶段::失败, "在跑的必须判失败，不猜成功");
        assert_eq!(九.节点.get("跑着的"), Some(&调用节点阶段::失败));
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

    /// 判据：坏行跳过，不连累其他行；文件不存在就是空快照。
    #[test]
    fn 坏行跳过且缺文件不报错() {
        let 路径 = 临时路径("坏行");
        std::fs::write(
            &路径,
            "{\"任务标识\":5,\"阶段\":\"成功\",\"节点\":{}}\n这不是JSON\n",
        )
        .unwrap();
        let 快照 = 任务落盘::指定路径(路径.clone()).读回();
        assert_eq!(
            快照.任务.get(&5).map(|条| 条.阶段),
            Some(调用任务阶段::成功)
        );
        assert_eq!(快照.任务.len(), 1, "坏行必须被跳过，不许造出半条记录");
        let _ = std::fs::remove_file(&路径);
        assert!(任务落盘::指定路径(路径).读回().任务.is_empty());
    }
}
