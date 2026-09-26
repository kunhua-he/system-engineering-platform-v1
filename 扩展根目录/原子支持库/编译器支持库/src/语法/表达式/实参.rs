//! 实参表 —— 调用实参 / 空实参 / 括号里那一段（[`super`] 的续篇）。
//!
//! `分析器` 的固有实现拆在两件里（本件只放实参表），**不是两套实现**。
//! 拆的原因只有一个：单文件 ≤ 400 行。

use super::分析器;
use crate::语言面::{记号种类, 节点种类};

impl 分析器<'_> {
    /// 实参表：`开` 是 `(` 的下标，`闭` 是配对的 `)` 的下标。
    ///
    /// **空位的锚**（照已冻的读数 `形状测试/语法树.rs::语法树_样例子树止与子区间`）：
    /// 空位是**零宽**节点，锚在**它前面那个逗号的起**；第一个实参就是空位时锚在 `(` 的止；
    /// `…, )` 的尾空位锚在它前面那个逗号。`(甲, , 乙)` ⇒ 空位 `[11,11)`（甲止 == 11）。
    ///
    /// 解不出的实参：把余下记号包成一个兜底叶，**不再往下切**（不 panic、不死循环）。
    pub(super) fn 实参表在(&mut self, 开: usize, 闭: usize) -> Vec<u32> {
        let 左止 = self.记号表[开].止;
        let mut 实参: Vec<u32> = Vec::new();
        let mut 游标 = 开 + 1;
        let mut 前分隔: Option<u32> = None;
        let mut 期待 = true;
        loop {
            // 跳过空白与花括号（`置入代码 ({ 139, 69, … })` 的 `{` / `}`）。
            while 游标 < 闭 {
                let t = self.记号表[游标];
                let 是花括号 =
                    t.种类 == 记号种类::界符 && (self.文(t) == b"{" || self.文(t) == b"}");
                if t.种类 == 记号种类::空白 || 是花括号 {
                    游标 += 1;
                } else {
                    break;
                }
            }
            if 游标 >= 闭 {
                if 期待
                    && let Some(锚) = 前分隔
                {
                    实参.push(self.草稿.叶(节点种类::空实参, 锚, 锚));
                }
                break;
            }
            let t = self.记号表[游标];
            if t.种类 == 记号种类::界符 && self.文(t) == b"," {
                if 期待 {
                    let 锚 = 前分隔.unwrap_or(左止);
                    实参.push(self.草稿.叶(节点种类::空实参, 锚, 锚));
                }
                前分隔 = Some(t.起);
                游标 += 1;
                期待 = true;
                continue;
            }
            let 保存游标 = self.游标;
            let 保存止 = self.止;
            self.游标 = 游标;
            self.止 = 闭;
            let 果 = self.二元();
            游标 = self.游标;
            self.游标 = 保存游标;
            self.止 = 保存止;
            match 果 {
                // **解出一个实参就不许兜底**：剩下的逗号与实参留给下一轮，
                // 否则 `(甲, 乙, 丙)` 会变成一个实参 + 一片兜底（实测撞到过）。
                Some(n) => {
                    实参.push(n);
                    期待 = false;
                }
                None => {
                    // 一个记号都没解出：余下包成一个兜底叶，收手（不 panic、不死循环）
                    if let Some(叶) = self.兜底到(闭) {
                        实参.push(叶);
                    }
                    break;
                }
            }
        }
        实参
    }

    /// 公开口：解析一整个实参表（`开` 给 `(` 的下标）。返回实参草稿下标表。
    pub(crate) fn 解析实参表(&mut self, 开: usize, 止: usize) -> Vec<u32> {
        let 保存游标 = self.游标;
        let 保存止 = self.止;
        self.游标 = 开;
        self.止 = 止;
        let 果 = match self.配对(b"(", b")") {
            Some(闭) => self.实参表在(开, 闭),
            None => Vec::new(),
        };
        self.游标 = 保存游标;
        self.止 = 保存止;
        果
    }

    /// 公开口：在 `[起, 止)` 里找第一个 `(` 并解析它里面的实参表（块头条件 / 置入代码用）。
    pub(crate) fn 解析括号实参(&mut self, 起: usize, 止: usize) -> Vec<u32> {
        let mut i = 起;
        while i < 止 {
            let t = self.记号表[i];
            if t.种类 == 记号种类::界符 && self.文(t) == b"(" {
                return self.解析实参表(i, 止);
            }
            i += 1;
        }
        Vec::new()
    }
}
