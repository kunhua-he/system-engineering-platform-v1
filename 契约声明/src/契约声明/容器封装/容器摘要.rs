//! 摘要 —— 零依赖 SHA-256（FIPS 180-4）。
//!
//! 从 `容器.rs` 拆出（拆分：一个关注点一个件，`开发规范.md` 第六节）：指纹段的内容是各段
//! 的 sha256，本件只管**算**；指纹段的编解码与容器形状仍在 `容器.rs`。

use alloc::vec::Vec;

use super::指纹宽度;

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
const 初始哈希值: [u32; 8] = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
];

/// SHA-256。
pub fn 算指纹(数据字节: &[u8]) -> [u8; 指纹宽度] {
    let mut 状态 = 初始哈希值;
    let mut 数据块 = Vec::with_capacity(数据字节.len() + 72);
    数据块.extend_from_slice(数据字节);
    数据块.push(0x80);
    // 补零至长度 ≡ 56 (mod 64)。
    while 数据块.len() % 64 != 56 {
        数据块.push(0);
    }
    // 末 8 字节：原数据的**位数**，大端。
    数据块.extend_from_slice(&(数据字节.len() as u64 * 8).to_be_bytes());

    for 片段 in 数据块.chunks_exact(64) {
        压缩状态(&mut 状态, 片段);
    }

    let mut 输出缓冲 = [0u8; 指纹宽度];
    for (序号, 字符表) in 状态.iter().enumerate() {
        输出缓冲[序号 * 4..序号 * 4 + 4].copy_from_slice(&字符表.to_be_bytes());
    }
    输出缓冲
}

fn 压缩状态(状态: &mut [u32; 8], 数据块: &[u8]) {
    let mut 字符表 = [0u32; 64];
    for 序号 in 0..16 {
        字符表[序号] = u32::from_be_bytes(数据块[序号 * 4..序号 * 4 + 4].try_into().unwrap());
    }
    for 序号 in 16..64 {
        let 小西格玛 = 字符表[序号 - 15].rotate_right(7) ^ 字符表[序号 - 15].rotate_right(18) ^ (字符表[序号 - 15] >> 3);
        let 大西格玛 = 字符表[序号 - 2].rotate_right(17) ^ 字符表[序号 - 2].rotate_right(19) ^ (字符表[序号 - 2] >> 10);
        字符表[序号] = 字符表[序号 - 16]
            .wrapping_add(小西格玛)
            .wrapping_add(字符表[序号 - 7])
            .wrapping_add(大西格玛);
    }

    let mut 轮状态 = *状态;

    for 序号 in 0..64 {
        let 大西格玛 = 轮状态[4].rotate_right(6) ^ 轮状态[4].rotate_right(11) ^ 轮状态[4].rotate_right(25);
        let 选择值 = (轮状态[4] & 轮状态[5]) ^ ((!轮状态[4]) & 轮状态[6]);
        let 轮压缩量 = 轮状态[7]
            .wrapping_add(大西格玛)
            .wrapping_add(选择值)
            .wrapping_add(轮常量[序号])
            .wrapping_add(字符表[序号]);
        let 小西格玛 = 轮状态[0].rotate_right(2) ^ 轮状态[0].rotate_right(13) ^ 轮状态[0].rotate_right(22);
        let 多数 = (轮状态[0] & 轮状态[1]) ^ (轮状态[0] & 轮状态[2]) ^ (轮状态[1] & 轮状态[2]);
        let 轮进位量 = 小西格玛.wrapping_add(多数);

        // 右移一位：第 4 位 += 轮压缩量，第 0 位 = 轮压缩量 + 轮进位量。
        // 数组字面量的各元素都取**旧值**（赋值在字面量求值之后）⇒ 与逐条赋值逐字等价。
        轮状态 = [
            轮压缩量.wrapping_add(轮进位量),
            轮状态[0],
            轮状态[1],
            轮状态[2],
            轮状态[3].wrapping_add(轮压缩量),
            轮状态[4],
            轮状态[5],
            轮状态[6],
        ];
    }

    for 序号 in 0..8 {
        状态[序号] = 状态[序号].wrapping_add(轮状态[序号]);
    }
}
