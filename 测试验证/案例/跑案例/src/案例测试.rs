//! 案例读盘的正/反向样本 —— 从 `案例.rs` 拆出（单源文件 ≤400 行的硬数）。
//!
//! 口径与 `案例.rs` 同源，不另立一套；`use super::*` 取它的读盘件与私有函数。

use super::*;

#[test]
fn 十六进制按空白分组也解得对() {
    assert_eq!(解十六进制("4e 4f 54").unwrap(), b"NOT");
    assert_eq!(解十六进制("0a0b").unwrap(), vec![0x0a, 0x0b]);
    assert!(解十六进制("4e4").is_err(), "奇数位该被拒");
    assert!(解十六进制("zz").is_err(), "非十六进制该被拒");
}

#[test]
fn 相对路按案例目录解_绝对路原样() {
    assert_eq!(解路(Path::new("/首目录/次目录"), Path::new("末件.txt")), PathBuf::from("/首目录/次目录/末件.txt"));
    assert_eq!(解路(Path::new("/首目录/次目录"), Path::new("/末目录/末子目录")), PathBuf::from("/末目录/末子目录"));
}

/// 反向样本：不认的 `来源` 必须报错，不许静默当成某个默认值。
#[test]
fn 不认的来源报错() {
    let 清单 = 最小JSON::解析(r#"{"步骤":[{"名":"首项","能力编号":1,"实参":[{"类型标签":4,"来源":"猜"}]}]}"#).unwrap();
    assert!(读步骤(&清单, Path::new("/首案例")).is_err());
}
