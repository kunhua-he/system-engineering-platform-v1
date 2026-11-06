use std::collections::{BTreeMap, BTreeSet, VecDeque};
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 资源租约 {
    pub 节点标识: String,
    pub 资源键: Vec<String>,
    pub 租约序号: u64,
}
#[derive(Debug, Default)]
pub struct 调用资源车道 {
    占用者: BTreeMap<String, String>,
    等待队列: BTreeMap<String, VecDeque<String>>,
    下一租约序号: u64,
}
impl 调用资源车道 {
    pub fn 构造() -> Self {
        Self::default()
    }
    pub fn 尝试预留(
        &mut self,
        节点标识: impl Into<String>,
        资源键: impl IntoIterator<Item = impl Into<String>>,
    ) -> Option<资源租约> {
        let 节点标识 = 节点标识.into();
        let 资源集合: BTreeSet<String> = 资源键.into_iter().map(Into::into).collect();
        let 资源键: Vec<String> = 资源集合.iter().cloned().collect();
        let 阻塞 = 资源集合.iter().any(|资源名称| {
            if self.占用者.contains_key(资源名称) {
                return true;
            }
            self.等待队列
                .get(资源名称)
                .is_some_and(|队列| 队列.front().is_some_and(|队首| 队首 != &节点标识))
        });
        if 阻塞 {
            for 资源名称 in &资源集合 {
                let 队列 = self.等待队列.entry(资源名称.clone()).or_default();
                if !队列.contains(&节点标识) {
                    队列.push_back(节点标识.clone());
                }
            }
            return None;
        }
        for 资源名称 in &资源集合 {
            if let Some(队列) = self
                .等待队列
                .get_mut(资源名称)
                .filter(|队列| 队列.front() == Some(&节点标识))
            {
                队列.pop_front();
            }
        }
        self.下一租约序号 += 1;
        for 资源名称 in &资源集合 {
            self.占用者.insert(资源名称.clone(), 节点标识.clone());
        }
        Some(资源租约 {
            节点标识,
            资源键,
            租约序号: self.下一租约序号,
        })
    }
    pub fn 释放(&mut self, 租约: &资源租约) -> bool {
        let mut 释放数 = 0;
        for 资源 in &租约.资源键 {
            if self.占用者.get(资源) == Some(&租约.节点标识) {
                self.占用者.remove(资源);
                释放数 += 1;
            }
        }
        释放数 == 租约.资源键.len()
    }
    pub fn 等待节点(&self, 资源键: &str) -> Option<&VecDeque<String>> {
        self.等待队列.get(资源键)
    }
}
