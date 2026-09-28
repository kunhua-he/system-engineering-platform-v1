//! 测试（整文件即测试，`lib.rs` 用 `#[cfg(test)] #[path]` 挂进来）。
//!
//! 每条分支都要有读数：覆盖 · macOS · Linux+XDG · Linux 无 XDG · Windows · 全缺。
//! 另外两条是**判据的反向样本**：① 默认位置不在源码树内 ② 四类子目录名两两不同。

use super::*;

fn 只覆盖<'a>(覆盖: &'a str) -> 解析环境<'a> {
    解析环境 {
        覆盖: Some(覆盖),
        ..Default::default()
    }
}

// ── 一 覆盖优先 ───────────────────────────────────────────────────────────

#[test]
fn 覆盖非空时原样用它_不再拼默认目录名() {
    let 根目录 = 解析(&只覆盖("/临时/我的根"), 平台::MacOS).expect("覆盖非空必成功");
    assert_eq!(根目录, std::path::PathBuf::from("/临时/我的根"));
    assert!(
        !根目录.to_string_lossy().contains(默认目录名),
        "覆盖是**完整根**：不许再拼一层 {默认目录名}（拼了就与部署方说的不是同一个位置）"
    );
}

#[test]
fn 覆盖为空串等于没给() {
    let 解析环境 = 解析环境 {
        覆盖: Some(""),
        家目录: Some("/家"),
        ..Default::default()
    };
    let 根目录 = 解析(&解析环境, 平台::MacOS).expect("空覆盖 ⇒ 退回默认");
    assert_eq!(根目录, std::path::PathBuf::from("/家/Library/Application Support").join(默认目录名));
}

// ── 二 三条平台规则 ───────────────────────────────────────────────────────

#[test]
fn 苹果系统_用应用支持目录() {
    let 解析环境 = 解析环境 {
        家目录: Some("/用户/我"),
        ..Default::default()
    };
    assert_eq!(
        解析(&解析环境, 平台::MacOS).unwrap(),
        std::path::PathBuf::from("/用户/我/Library/Application Support").join(默认目录名)
    );
}

#[test]
fn linux_设了数据目录变量就用它() {
    let 解析环境 = 解析环境 {
        xdg数据目录: Some("/数据"),
        家目录: Some("/家"),
        ..Default::default()
    };
    assert_eq!(
        解析(&解析环境, 平台::Linux).unwrap(),
        std::path::PathBuf::from("/数据").join(默认目录名),
        "XDG_DATA_HOME 设了就必须用它，不许看家目录"
    );
}

#[test]
fn linux_没设数据目录变量就退回家目录下() {
    let 解析环境 = 解析环境 {
        家目录: Some("/家"),
        ..Default::default()
    };
    assert_eq!(
        解析(&解析环境, 平台::Linux).unwrap(),
        std::path::PathBuf::from("/家/.local/share").join(默认目录名)
    );
}

#[test]
fn 视窗系统_用应用数据目录而不是家目录() {
    let 解析环境 = 解析环境 {
        应用数据目录: Some("C:\\数据"),
        家目录: Some("C:\\用户\\我"),
        ..Default::default()
    };
    assert_eq!(
        解析(&解析环境, 平台::Windows).unwrap(),
        std::path::PathBuf::from("C:\\数据").join(默认目录名),
        "APPDATA 与家目录是两处，别混"
    );
}

#[test]
fn 全缺时结构化失败_不编一个路径() {
    let 空环境 = 解析环境::default();
    assert_eq!(解析(&空环境, 平台::MacOS), Err(解析失败::无位置));
    assert_eq!(解析(&空环境, 平台::Linux), Err(解析失败::无位置));
    assert_eq!(解析(&空环境, 平台::Windows), Err(解析失败::无位置));
}

#[test]
fn 空串与缺失同义_不算有值() {
    let 解析环境 = 解析环境 {
        家目录: Some(""),
        ..Default::default()
    };
    assert_eq!(解析(&解析环境, 平台::MacOS), Err(解析失败::无位置));
}

// ── 三 判据的反向样本 ─────────────────────────────────────────────────────

/// **默认位置永不在源码树内** —— 三条规则各来一次，断言结果既绝对、也不以当前目录为前缀。
///
/// 反向样本：把任一条规则改成 `PathBuf::from(".")`（落在源码树里），本用例当场红。
#[test]
fn 默认位置不在源码树内_三条规则都推不出当前目录() {
    let 当前 = std::env::current_dir().expect("取当前目录");
    let 样本: [(平台, 解析环境); 4] = [
        (
            平台::MacOS,
            解析环境 {
                家目录: Some("/家"),
                ..Default::default()
            },
        ),
        (
            平台::Linux,
            解析环境 {
                xdg数据目录: Some("/数据"),
                ..Default::default()
            },
        ),
        (
            平台::Linux,
            解析环境 {
                家目录: Some("/家"),
                ..Default::default()
            },
        ),
        (
            平台::Windows,
            解析环境 {
                应用数据目录: Some("/数据"),
                ..Default::default()
            },
        ),
    ];
    for (平台, 解析环境) in 样本 {
        let 根目录 = 解析(&解析环境, 平台).expect("该分支必推得出");
        assert!(根目录.is_absolute(), "默认位置必须绝对：{根目录:?}");
        assert!(
            !根目录.starts_with(&当前),
            "默认位置不许落在当前目录（源码树）下：{根目录:?}"
        );
    }
}

/// 四类子目录：名字两两不同，且次序与判别值一致。
///
/// 反向样本：把两类写成同一个目录名（复制粘贴错），本用例当场红。
#[test]
fn 四类子目录_名字两两不同_次序与判别值一致() {
    for (序号, 类别) in 子目录::全集.iter().enumerate() {
        assert_eq!(*类别 as usize, 序号, "次序必须与判别值一致：{类别:?}");
    }
    for (前项序, 前项) in 子目录::全集.iter().enumerate() {
        for 后项 in &子目录::全集[前项序 + 1..] {
            assert_ne!(前项.取名称(), 后项.取名称(), "两类不许同名：{前项:?} 与 {后项:?}");
        }
    }
}

// ── 四 建目录 ─────────────────────────────────────────────────────────────

#[test]
fn 确保子目录真建得出来() {
    let 根目录 = std::env::temp_dir().join(format!(
        "v1-运行数据根-测试-{}",
        std::process::id()
    ));
    let _ = std::fs::remove_dir_all(&根目录);
    for 类别 in 子目录::全集 {
        let 路径 = 确保子目录(&根目录, 类别).expect("建目录");
        assert!(路径.is_dir(), "必须真建出目录：{路径:?}");
        assert!(路径.ends_with(类别.取名称()));
    }
    let _ = std::fs::remove_dir_all(&根目录);
}

#[test]
fn 子目录路径只拼不建() {
    let 根目录 = std::env::temp_dir().join("v1-运行数据根-只拼-不存在");
    let 路径 = 子目录路径(&根目录, 子目录::日志);
    assert_eq!(路径, 根目录.join("日志"));
    assert!(!路径.exists(), "只拼路径不许有副作用（建目录是另一件事）");
}
