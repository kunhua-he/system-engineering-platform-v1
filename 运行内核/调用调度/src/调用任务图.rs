use std::collections::{BTreeMap, BTreeSet, VecDeque};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 调用任务节点 {
    pub 节点标识: String,
    pub 依赖节点: Vec<String>,
}
impl 调用任务节点 {
    pub fn 构造(
        节点标识: impl Into<String>,
        依赖节点: impl IntoIterator<Item = impl Into<String>>,
    ) -> Self {
        Self {
            节点标识: 节点标识.into(),
            依赖节点: 依赖节点.into_iter().map(Into::into).collect(),
        }
    }
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum 图校验错误 {
    空图,
    空节点标识,
    重复节点标识(String),
    重复依赖(String, String),
    未知依赖(String, String),
    自依赖(String),
    有环,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct 调用任务图 {
    节点: Vec<调用任务节点>,
    索引: BTreeMap<String, usize>,
    后继: Vec<Vec<usize>>,
    拓扑序: Vec<usize>,
}
impl 调用任务图 {
    pub fn 构造图(节点: Vec<调用任务节点>) -> Result<Self, 图校验错误> {
        if 节点.is_empty() {
            return Err(图校验错误::空图);
        };
        let mut 索引 = BTreeMap::new();
        for (节点序号, 节点项) in 节点.iter().enumerate() {
            if 节点项.节点标识.is_empty() {
                return Err(图校验错误::空节点标识);
            }
            if 索引.insert(节点项.节点标识.clone(), 节点序号).is_some() {
                return Err(图校验错误::重复节点标识(节点项.节点标识.clone()));
            }
        }
        let mut 后继 = vec![Vec::new(); 节点.len()];
        let mut 入度 = vec![0usize; 节点.len()];
        for (节点序号, 节点项) in 节点.iter().enumerate() {
            let mut 依赖集合 = BTreeSet::new();
            for 依赖 in &节点项.依赖节点 {
                if 依赖 == &节点项.节点标识 {
                    return Err(图校验错误::自依赖(节点项.节点标识.clone()));
                }
                if !依赖集合.insert(依赖) {
                    return Err(图校验错误::重复依赖(
                        节点项.节点标识.clone(),
                        依赖.clone(),
                    ));
                }
                let Some(&前置) = 索引.get(依赖) else {
                    return Err(图校验错误::未知依赖(
                        节点项.节点标识.clone(),
                        依赖.clone(),
                    ));
                };
                后继[前置].push(节点序号);
                入度[节点序号] += 1;
            }
        }
        let mut 队列 = VecDeque::new();
        for (节点序号, 度数) in 入度.iter().enumerate() {
            if *度数 == 0 {
                队列.push_back(节点序号)
            }
        }
        let mut 拓扑序 = Vec::with_capacity(节点.len());
        while let Some(节点序号) = 队列.pop_front() {
            拓扑序.push(节点序号);
            for &后置 in &后继[节点序号] {
                入度[后置] -= 1;
                if 入度[后置] == 0 {
                    队列.push_back(后置)
                }
            }
        }
        if 拓扑序.len() != 节点.len() {
            return Err(图校验错误::有环);
        }
        Ok(Self {
            节点,
            索引,
            后继,
            拓扑序,
        })
    }
    pub fn 节点(&self, 标识: &str) -> Option<&调用任务节点> {
        self.索引.get(标识).map(|&节点序号| &self.节点[节点序号])
    }
    pub fn 后继节点(&self, 标识: &str) -> Option<impl Iterator<Item = &str>> {
        let &节点序号 = self.索引.get(标识)?;
        Some(
            self.后继[节点序号]
                .iter()
                .map(|&后置| self.节点[后置].节点标识.as_str()),
        )
    }
    pub fn 拓扑序(&self) -> impl Iterator<Item = &str> {
        self.拓扑序
            .iter()
            .map(|&节点序号| self.节点[节点序号].节点标识.as_str())
    }
    pub(crate) fn 节点列表(&self) -> &[调用任务节点] {
        &self.节点
    }
}
