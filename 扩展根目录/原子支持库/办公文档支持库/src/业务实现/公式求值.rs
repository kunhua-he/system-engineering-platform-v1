//! 公式求值：四则运算 + 括号 + 变量名，以及变量表（JSON 对象）解析。

use crate::编号与码面::错误码;

use super::基础件::最大变量个数;

// ── 公式求值：四则运算 + 括号 + 变量名 ──────────────────────────

pub(super) fn 求值(公式文本: &str, 变量表: &[(String, f64)]) -> Result<f64, u32> {
    let 字序: Vec<char> = 公式文本.chars().filter(|单字元| !单字元.is_whitespace()).collect();
    if 字序.is_empty() {
        return Err(错误码::计算失败);
    }
    let mut 游标 = 0usize;
    let 结果值 = 解析加减(&字序, &mut 游标, 变量表)?;
    if 游标 != 字序.len() {
        return Err(错误码::计算失败);
    }
    if !结果值.is_finite() {
        return Err(错误码::计算失败);
    }
    Ok(结果值)
}

fn 解析加减(字序: &[char], 游标: &mut usize, 变量表: &[(String, f64)]) -> Result<f64, u32> {
    let mut 累积值 = 解析乘除(字序, 游标, 变量表)?;
    while *游标 < 字序.len() {
        let 运算符 = 字序[*游标];
        if 运算符 != '+' && 运算符 != '-' {
            break;
        }
        *游标 += 1;
        let 右值 = 解析乘除(字序, 游标, 变量表)?;
        累积值 = if 运算符 == '+' { 累积值 + 右值 } else { 累积值 - 右值 };
    }
    Ok(累积值)
}

fn 解析乘除(字序: &[char], 游标: &mut usize, 变量表: &[(String, f64)]) -> Result<f64, u32> {
    let mut 累积值 = 解析单元(字序, 游标, 变量表)?;
    while *游标 < 字序.len() {
        let 运算符 = 字序[*游标];
        if 运算符 != '*' && 运算符 != '/' {
            break;
        }
        *游标 += 1;
        let 右值 = 解析单元(字序, 游标, 变量表)?;
        if 运算符 == '*' {
            累积值 *= 右值;
        } else {
            if 右值 == 0.0 {
                return Err(错误码::计算失败);
            }
            累积值 /= 右值;
        }
    }
    Ok(累积值)
}

fn 解析单元(字序: &[char], 游标: &mut usize, 变量表: &[(String, f64)]) -> Result<f64, u32> {
    if *游标 >= 字序.len() {
        return Err(错误码::计算失败);
    }
    let 当前字元 = 字序[*游标];
    if 当前字元 == '-' {
        *游标 += 1;
        return Ok(-解析单元(字序, 游标, 变量表)?);
    }
    if 当前字元 == '+' {
        *游标 += 1;
        return 解析单元(字序, 游标, 变量表);
    }
    if 当前字元 == '(' {
        *游标 += 1;
        let 内部值 = 解析加减(字序, 游标, 变量表)?;
        if *游标 >= 字序.len() || 字序[*游标] != ')' {
            return Err(错误码::计算失败);
        }
        *游标 += 1;
        return Ok(内部值);
    }
    if 当前字元.is_ascii_digit() || 当前字元 == '.' {
        return 解析数字(字序, 游标);
    }
    if 当前字元.is_alphabetic() || 当前字元 == '_' {
        let 起始位 = *游标;
        while *游标 < 字序.len()
            && (字序[*游标].is_alphanumeric() || 字序[*游标] == '_')
        {
            *游标 += 1;
        }
        let 变量名: String = 字序[起始位..*游标].iter().collect();
        return 查变量(变量表, &变量名);
    }
    Err(错误码::计算失败)
}

fn 解析数字(字序: &[char], 游标: &mut usize) -> Result<f64, u32> {
    let 起始位 = *游标;
    let mut 见到小数点 = false;
    while *游标 < 字序.len() {
        let 当前字元 = 字序[*游标];
        if 当前字元.is_ascii_digit() {
            *游标 += 1;
            continue;
        }
        if 当前字元 == '.' && !见到小数点 {
            见到小数点 = true;
            *游标 += 1;
            continue;
        }
        break;
    }
    let 数字文本: String = 字序[起始位..*游标].iter().collect();
    数字文本.parse::<f64>().map_err(|_| 错误码::计算失败)
}

fn 查变量(变量表: &[(String, f64)], 变量名: &str) -> Result<f64, u32> {
    for (名字, 取值) in 变量表 {
        if 名字 == 变量名 {
            return Ok(*取值);
        }
    }
    Err(错误码::计算失败)
}

pub(super) fn 数值转文本(算式结果: f64) -> String {
    if 算式结果 == 算式结果.trunc() && 算式结果.abs() < 1e15 {
        return format!("{}", 算式结果 as i64);
    }
    let 粗文本 = format!("{}", 算式结果);
    粗文本
}

// ── 变量表解析：只接受 JSON 对象，值必须是数值 ──────────────────

pub(super) fn 解析变量表(变量文本: &str) -> Result<Vec<(String, f64)>, u32> {
    let 字序: Vec<char> = 变量文本.chars().collect();
    let mut 游标 = 0usize;
    let mut 变量表: Vec<(String, f64)> = Vec::new();
    跳过空白(&字序, &mut 游标);
    if 游标 >= 字序.len() || 字序[游标] != '{' {
        return Err(错误码::参数不合法);
    }
    游标 += 1;
    跳过空白(&字序, &mut 游标);
    if 游标 < 字序.len() && 字序[游标] == '}' {
        return Ok(变量表);
    }
    loop {
        if 变量表.len() >= 最大变量个数 {
            return Err(错误码::内容不合法);
        }
        跳过空白(&字序, &mut 游标);
        let 名字 = 读名字(&字序, &mut 游标)?;
        跳过空白(&字序, &mut 游标);
        if 游标 >= 字序.len() || 字序[游标] != ':' {
            return Err(错误码::参数不合法);
        }
        游标 += 1;
        跳过空白(&字序, &mut 游标);
        let 取值 = 读数值(&字序, &mut 游标)?;
        变量表.push((名字, 取值));
        跳过空白(&字序, &mut 游标);
        if 游标 >= 字序.len() {
            return Err(错误码::参数不合法);
        }
        if 字序[游标] == ',' {
            游标 += 1;
            continue;
        }
        if 字序[游标] == '}' {
            return Ok(变量表);
        }
        return Err(错误码::参数不合法);
    }
}

fn 跳过空白(字序: &[char], 游标: &mut usize) {
    while *游标 < 字序.len() && 字序[*游标].is_whitespace() {
        *游标 += 1;
    }
}

fn 读名字(字序: &[char], 游标: &mut usize) -> Result<String, u32> {
    if *游标 >= 字序.len() || 字序[*游标] != '"' {
        return Err(错误码::参数不合法);
    }
    *游标 += 1;
    let mut 名字 = String::new();
    while *游标 < 字序.len() {
        let 当前字元 = 字序[*游标];
        if 当前字元 == '\\' {
            *游标 += 1;
            if *游标 >= 字序.len() {
                return Err(错误码::参数不合法);
            }
            名字.push(字序[*游标]);
            *游标 += 1;
            continue;
        }
        if 当前字元 == '"' {
            *游标 += 1;
            return Ok(名字);
        }
        名字.push(当前字元);
        *游标 += 1;
    }
    Err(错误码::参数不合法)
}

fn 读数值(字序: &[char], 游标: &mut usize) -> Result<f64, u32> {
    let 起始位 = *游标;
    while *游标 < 字序.len() {
        let 当前字元 = 字序[*游标];
        if 当前字元.is_ascii_digit()
            || 当前字元 == '-'
            || 当前字元 == '+'
            || 当前字元 == '.'
            || 当前字元 == 'e'
            || 当前字元 == 'E'
        {
            *游标 += 1;
            continue;
        }
        break;
    }
    if *游标 == 起始位 {
        return Err(错误码::参数不合法);
    }
    let 数字文本: String = 字序[起始位..*游标].iter().collect();
    数字文本.parse::<f64>().map_err(|_| 错误码::参数不合法)
}
