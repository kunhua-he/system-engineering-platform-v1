//! 指纹段编码 + 自带的 SHA-256 —— 能力包件**第三段**（段类型号 `18`）的内容。
//!
//! `能力包件.md` §一：指纹段装「各段的 sha256」，agent 看不到，**判据自用**。
//! §四 给了它存在的理由：接口说明与机器码必须在同一个文件里，**同封装之后指纹段可以给
//! 两者各算一个哈希，任何一边被换过都判得出来**。
//!
//! # 为什么 SHA-256 自己写一遍，不用现成库
//!
//! `代码形态分工.md` §五 硬判据 4：**进制品的形态必须零第三方依赖**（Rust crate 一律只用 `std`）。
//! `Cargo.lock` 里没有 sha2 / ring 一类，而指纹段是包件三段的承重部分（边被换过就判不出来）。
//! ⇒ 照仓内既有做法自己写一份，并以 **NIST 已知向量**当场验证（测试件里播 `""` 与 `"abc"` 两条）。
//!
//! # 指纹段自己的字节排布
//!
//! 它**不能把自身的哈希也算进去**（自指）⇒ 只登前两段：
//!
//! ```text
//! u32 条数 · 每条 ( u8 段类型号 + 32 字节 sha256 )
//! ```
//!
//! 哈希的对象是该段**数据**（不拿段头算：段头由段名与段类型确定，改段名也会改数据以外的东西，
//! 而本段的职责是「码与说明没被换过」——数据就是它们）。条数固定 2（接口说明 · 能力码）。

/// 指纹的字节宽（sha256）。
pub const 指纹宽度: usize = 32;

/// 一段的指纹项：段类型号 + 该段数据的 sha256。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct 段指纹 {
    pub 段类型号: u8,
    pub 哈希: [u8; 指纹宽度],
}

/// 算一份指纹段数据：逐段哈希后按下表拼起。
pub fn 编码(段们: &[(u8, &[u8])]) -> Vec<u8> {
    let mut 出 = Vec::new();
    出.extend_from_slice(&(段们.len() as u32).to_le_bytes());
    for (号, 数据) in 段们 {
        出.push(*号);
        出.extend_from_slice(&算指纹(数据));
    }
    出
}

/// 指纹段数据 → 项表。`None` = 截断 / 尾部多余字节。
///
/// **本函数只做形状解，不重算哈希**：重算要拿原段数据，那是**校验方**的事
/// （它手上有整个包，可以反解出两段再比）。本件不把「校验」与「解形状」搌成一个口。
pub fn 解码(字节: &[u8]) -> Option<Vec<段指纹>> {
    if 字节.len() < 4 {
        return None;
    }
    let 条数 = u32::from_le_bytes(字节[..4].try_into().ok()?) as usize;
    let 每项 = 1 + 指纹宽度;
    if 字节.len() - 4 != 条数 * 每项 {
        return None;
    }
    let mut 出 = Vec::with_capacity(条数);
    for 序 in 0..条数 {
        let 起 = 4 + 序 * 每项;
        let mut 哈希 = [0u8; 指纹宽度];
        哈希.copy_from_slice(&字节[起 + 1..起 + 每项]);
        出.push(段指纹 { 段类型号: 字节[起], 哈希 });
    }
    Some(出)
}

// ─────────────────────────────────────────────────────────────────────────────
// SHA-256（FIPS 180-4）—— 零依赖自实现。
// ─────────────────────────────────────────────────────────────────────────────

/// 轮常量（前 64 个质数立方根小数部的头 32 位）。
const 轮常量: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

/// 初始哈希值（前 8 个质数平方根小数部的头 32 位）。
const 初始值: [u32; 8] = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
];

/// SHA-256。
pub fn 算指纹(数据: &[u8]) -> [u8; 指纹宽度] {
    let mut 状态 = 初始值;
    let mut 块 = Vec::with_capacity(数据.len() + 72);
    块.extend_from_slice(数据);
    块.push(0x80);
    // 补零至长度 ≡ 56 (mod 64)。
    while 块.len() % 64 != 56 {
        块.push(0);
    }
    // 末 8 字节：原数据的**位数**，大端。
    块.extend_from_slice(&(数据.len() as u64 * 8).to_be_bytes());

    for 片 in 块.chunks_exact(64) {
        压缩(&mut 状态, 片);
    }

    let mut 出 = [0u8; 指纹宽度];
    for (序, 字) in 状态.iter().enumerate() {
        出[序 * 4..序 * 4 + 4].copy_from_slice(&字.to_be_bytes());
    }
    出
}

fn 压缩(状态: &mut [u32; 8], 块: &[u8]) {
    let mut 字 = [0u32; 64];
    for 序 in 0..16 {
        字[序] = u32::from_be_bytes(块[序 * 4..序 * 4 + 4].try_into().unwrap());
    }
    for 序 in 16..64 {
        let s0 = 字[序 - 15].rotate_right(7) ^ 字[序 - 15].rotate_right(18) ^ (字[序 - 15] >> 3);
        let s1 = 字[序 - 2].rotate_right(17) ^ 字[序 - 2].rotate_right(19) ^ (字[序 - 2] >> 10);
        字[序] = 字[序 - 16]
            .wrapping_add(s0)
            .wrapping_add(字[序 - 7])
            .wrapping_add(s1);
    }

    let mut a = 状态[0];
    let mut b = 状态[1];
    let mut c = 状态[2];
    let mut d = 状态[3];
    let mut e = 状态[4];
    let mut f = 状态[5];
    let mut g = 状态[6];
    let mut h = 状态[7];

    for 序 in 0..64 {
        let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
        let 择 = (e & f) ^ ((!e) & g);
        let 临时1 = h
            .wrapping_add(s1)
            .wrapping_add(择)
            .wrapping_add(轮常量[序])
            .wrapping_add(字[序]);
        let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
        let 多数 = (a & b) ^ (a & c) ^ (b & c);
        let 临时2 = s0.wrapping_add(多数);

        h = g;
        g = f;
        f = e;
        e = d.wrapping_add(临时1);
        d = c;
        c = b;
        b = a;
        a = 临时1.wrapping_add(临时2);
    }

    状态[0] = 状态[0].wrapping_add(a);
    状态[1] = 状态[1].wrapping_add(b);
    状态[2] = 状态[2].wrapping_add(c);
    状态[3] = 状态[3].wrapping_add(d);
    状态[4] = 状态[4].wrapping_add(e);
    状态[5] = 状态[5].wrapping_add(f);
    状态[6] = 状态[6].wrapping_add(g);
    状态[7] = 状态[7].wrapping_add(h);
}
