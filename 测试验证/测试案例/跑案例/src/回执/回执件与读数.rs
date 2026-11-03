use crate::错误码::错误码登记;

/// 回执文件名。住在案例根下，与案例目录并列。
///
/// ★ **与读它的那一侧同名**（2026-09-30 收口）：读方是网关
/// `对外接口面/调用接口面/src/契约级常量.rs::案例回执件`。跨 crate（`v1-gateway` ↔ 本 crate）
/// 没法复用实现（网关不依赖 `契约声明/`，见它 Cargo.toml 的「跳层」注）⇒ 按
/// 「跨层复用同名」办：两侧一律叫 `案例回执件`，一侧改名另一侧一眼可见。
pub const 案例回执件: &str = "运行回执.jsonl";

/// 回执相对仓根的路径。**它不参与「工作区是否干净」的判定**（见文件头）。
pub const 回执相对路径: &str = "测试验证/测试案例/运行回执.jsonl";

/// 一条步骤读数。
#[derive(Debug, Clone)]
pub struct 步骤读数 {
    pub 名字: String,
    /// 步骤种类：`能力` / `通知`。通知步骤的 `能力编号` 恒 0（通知号另记在 `名` 与说明里）。
    pub 扩展种类: String,
    pub 能力编号: u32,
    /// 适配器当场取到的能力名；`None` = 这个号没被任何已装载声明认领。
    pub 能力名: Option<String>,
    /// **这次调用**的结果：`成功` / `失败`（平台那一侧的结果，不是案例判定）。
    ///
    /// 与 [`步骤读数::符合期望`] 分开是**必须的**：「调 1101 期望它失败」这条案例里，
    /// 调用结果是 `失败`、判定结果是 `符合期望`。合成一个字段，读者会把
    /// 「案例通过」误读成「能力可用」——那正是假绿。
    pub 调用结果: String,
    /// 这一步是否符合 `期望.json` 写的那一条。
    pub 符合期望: bool,
    pub 死在哪一层: Option<String>,
    pub 死在哪一步: Option<String>,
    pub 错误码: Option<错误码登记>,
    pub 耗时微秒: u128,
    /// 一句话读数（人读；机器只读上面那些字段）。
    pub 说明: String,
}

/// 一个案例一行。
#[derive(Debug, Clone)]
pub struct 回执 {
    pub 提交哈希: String,
    pub 工作区是否干净: bool,
    pub 案例名: String,
    pub 调用结局: String,
    pub 死在哪一层: Option<String>,
    pub 死在哪一步: Option<String>,
    pub 错误码: Option<错误码登记>,
    pub 耗时微秒: u128,
    pub 跑的时间: String,
    pub 说明: String,
    pub 案例步骤: Vec<步骤读数>,
}

impl 回执 {
    /// 一行 JSON（**没有换行**，追加时补）。
    pub fn 写成一行(&self) -> String {
        let mut 文本缓冲 = String::from("{");
        文本缓冲.push_str("\"提交哈希\":");
        crate::最小JSON::写串(&mut 文本缓冲, &self.提交哈希);
        文本缓冲.push_str(&format!(",\"工作区是否干净\":{}", self.工作区是否干净));
        文本缓冲.push_str(",\"案例名\":");
        crate::最小JSON::写串(&mut 文本缓冲, &self.案例名);
        文本缓冲.push_str(",\"结果\":");
        crate::最小JSON::写串(&mut 文本缓冲, &self.调用结局);
        文本缓冲.push_str(",\"死在哪一层\":");
        写可选串(&mut 文本缓冲, self.死在哪一层.as_deref());
        文本缓冲.push_str(",\"死在哪一步\":");
        写可选串(&mut 文本缓冲, self.死在哪一步.as_deref());
        文本缓冲.push_str(",\"错误码\":");
        match &self.错误码 {
            Some(错误码) => 文本缓冲.push_str(&错误码.转JSON文本()),
            None => 文本缓冲.push_str("null"),
        }
        文本缓冲.push_str(&format!(",\"耗时微秒\":{}", self.耗时微秒));
        文本缓冲.push_str(",\"跑的时间\":");
        crate::最小JSON::写串(&mut 文本缓冲, &self.跑的时间);
        文本缓冲.push_str(",\"说明\":");
        crate::最小JSON::写串(&mut 文本缓冲, &self.说明);
        文本缓冲.push_str(",\"步骤\":[");
        for (序号, 步序) in self.案例步骤.iter().enumerate() {
            if 序号 > 0 {
                文本缓冲.push(',');
            }
            文本缓冲.push('{');
            文本缓冲.push_str("\"名\":");
            crate::最小JSON::写串(&mut 文本缓冲, &步序.名字);
            文本缓冲.push_str(",\"种类\":");
            crate::最小JSON::写串(&mut 文本缓冲, &步序.扩展种类);
            文本缓冲.push_str(&format!(",\"能力编号\":{},\"能力名\":", 步序.能力编号));
            写可选串(&mut 文本缓冲, 步序.能力名.as_deref());
            文本缓冲.push_str(",\"调用结果\":");
            crate::最小JSON::写串(&mut 文本缓冲, &步序.调用结果);
            文本缓冲.push_str(&format!(",\"符合期望\":{}", 步序.符合期望));
            文本缓冲.push_str(",\"死在哪一层\":");
            写可选串(&mut 文本缓冲, 步序.死在哪一层.as_deref());
            文本缓冲.push_str(",\"死在哪一步\":");
            写可选串(&mut 文本缓冲, 步序.死在哪一步.as_deref());
            文本缓冲.push_str(",\"错误码\":");
            match &步序.错误码 {
                Some(错误码) => 文本缓冲.push_str(&错误码.转JSON文本()),
                None => 文本缓冲.push_str("null"),
            }
            文本缓冲.push_str(&format!(",\"耗时微秒\":{},\"说明\":", 步序.耗时微秒));
            crate::最小JSON::写串(&mut 文本缓冲, &步序.说明);
            文本缓冲.push('}');
        }
        文本缓冲.push_str("]}");
        文本缓冲
    }
}

pub(super) fn 写可选串(文本缓冲: &mut String, 待处理值: Option<&str>) {
    match 待处理值 {
        Some(源文本) => crate::最小JSON::写串(文本缓冲, 源文本),
        None => 文本缓冲.push_str("null"),
    }
}
