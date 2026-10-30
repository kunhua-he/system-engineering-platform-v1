// 时刻一律 YYYY-MM-DD HH:MM:SS、定宽 19 字符；定宽下字典序 == 时间序，比较不必解析成时间值。
pub fn 校验时刻(时刻串: &str) -> bool {
    let 字节表 = 时刻串.as_bytes();
    if 字节表.len() != 19 {
        return false;
    }
    if 字节表[4] != b'-'
        || 字节表[7] != b'-'
        || 字节表[10] != b' '
        || 字节表[13] != b':'
        || 字节表[16] != b':'
    {
        return false;
    }
    let 数字位: [usize; 14] = [0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18];
    for 位序 in 数字位 {
        if !字节表[位序].is_ascii_digit() {
            return false;
        }
    }
    let 月份值: u32 = 时刻串[5..7].parse().unwrap_or(0);
    let 日值: u32 = 时刻串[8..10].parse().unwrap_or(0);
    let 时值: u32 = 时刻串[11..13].parse().unwrap_or(99);
    let 分值: u32 = 时刻串[14..16].parse().unwrap_or(99);
    let 秒值: u32 = 时刻串[17..19].parse().unwrap_or(99);
    (1..=12).contains(&月份值)
        && (1..=31).contains(&日值)
        && 时值 < 24
        && 分值 < 60
        && 秒值 < 60
}

// 行首按「前缀长度」截一段，再从中取前 19 字符当时间戳；不成型一律 None（计入无法解析行）
pub fn 拆时刻与正文(原行: &str, 前缀长度: usize) -> Option<(String, String)> {
    let 行首: String = 原行.chars().take(前缀长度).collect();
    let 时刻候选: String = 行首.chars().take(19).collect();
    if !校验时刻(&时刻候选) {
        return None;
    }
    let 正文: String = 原行.chars().skip(前缀长度).collect();
    Some((时刻候选, 正文.trim().to_owned()))
}
