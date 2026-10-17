//! 装载件缓存 —— 能力包件解包物的**仓外落点**（与 `开发工具/取证/声明记录区反解/运行数据根.py`
//! 同形：可丢 · 可重建 · 丢了关缓存照常算）。
//!
//! # 为什么在这里
//!
//! 底座装载支持库要 `dlopen` **本机机器码**，而制品（`.支持库制品`）是**能力包件** —— 拿它直接
//! `dlopen` 必失败（`扫扩展根.rs` 文件头）。所以装载前的必经一步是：按容器解包（
//! `v1_contract::容器`，唯一 codec）取**能力码段**字节 → 落一份**真文件** → 再 `dlopen`。
//!
//! 落点**不许**是源码树（`README.md` §十 · 判据 ⑳）也**不许**自拼路径（判据 ㉕）⇒ 唯一落点是
//! **运行数据根**的**缓存**类。`对外接口面` 按层序拿不到 `运行内核/运行数据根`（跳层）
//! ⇒ 由本层（它唯一的腿）提供这一口。
//!
//! # 解析不出根
//!
//! [`默认缓存根目录`] 返回 `None`（**不退回源码树、不退回 `/tmp`**）—— 调用方据此把它当
//! **结构化失败**报出（该子目录剔除并报因），绝不静默落进源码树。
//!
//! # 四件事不是同一件事
//!
//! 本件要判的四件事，各自的**判据面**与**失败含义**都不同，混在一处就分不清是哪一层出的问题：
//!
//! | 一件 | 只回答什么 | 落点 | 判据面 |
//! |---|---|---|---|
//! | **内容校验** | 这串字节是不是它自称的能力包件 | [`校验内容`] | 只吃字节，路径不参与 |
//! | **来源信任** | 这条来源路径信不信得过 | [`判定来源信任`] | 只吃路径，字节不参与 |
//! | **路径对象** | 这条落点路径链能不能落 | [`缓存路径对象`] | 只吃路径链，与字节无关 |
//! | **缓存写入** | 把这段字节落到这条路径上 | [`写入缓存件`] | 吃「字节 + 落点」这一对 |
//!
//! # 上限与权限位：不读爆、不被别人改
//!
//! 上界与权限位都是**装载面的硬前提**，不是偏好：
//!
//! | 一条 | 回答什么 | 不过时 |
//! |---|---|---|
//! | **字节上限** | 这份制品配不配被读进来 | 拒（在 `fs::read` **之前**判，不读爆内存） |
//! | **权限位** | 这份缓存件别人能不能改 | 拒（组/他人可写 = 校验过的那份字节可能被换掉） |
//! | **候选择源** | 同一制品有多条来源时用哪条 | 全不可信则逐条报因（不允许「随便挑一条」） |
//!
//! 三者的落点都在本件（它们全部只关于「从盘上取一份字节」这一件事）。
//!
//! 四者的**名字**（缓存件名）另由 [`由内容算`] 定 —— `内容 → 名`，与来源、与落点都无关。
//! 编排只有一处：[`解包到缓存`] 按「来源 → 内容 → 名 → 写」四步各调各的，
//! **一个都不代另一个判**（拿来源可信当内容没坏，或拿内容没坏当落点可落，都是漏判）。

use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use v1_contract::容器;
use v1_dataroot::{子目录, 子目录路径, 解析当前环境};

/// 支持库能力码段的字节上限（64 MiB）。
///
/// **为什么要有**：旧形状是 `fs::read` 一口气读进来 —— 一份几十 GB 的制品会把底座读爆
/// （内存不是无限，而产物能不能被读进来是**装载面的前提**，不是调用方的自由）。
/// 取 64 MiB：本机两个真支持库产物的能力码段都在它以内若干数量级；它是「明显不可能」那条线，
/// 不是「优化」那条线（改它要重新裁一次并说明读数）。
pub const 能力码字节上限: u64 = 64 * 1024 * 1024;

/// 模块本机执行体段的字节上限（64 MiB）。
///
/// 与 [`能力码字节上限`] 同值但**不同一条**：两者判的是两个段、两条装载腿（支持库走码段、
/// 模块走执行体段）。合成一个名字会让「支持库把模块的线拉紧」变成一件不可读的事。
pub const 执行体字节上限: u64 = 64 * 1024 * 1024;

/// 缓存目录里的**缓存件条数上限**（256）。
///
/// **为什么要有**：缓存件按内容指纹定键、**永不自动删** —— 没有条数上界时，反复换制品会把
/// 缓存目录撑到无界（每个键一份文件，键随内容变）。取 256：本机真实制品个位数，
/// 256 是「明显够用、又不会无界」那条线，不是「优化」那条线（改它要重新裁一次并说明读数）。
///
/// 与 [`能力码字节上限`] / [`执行体字节上限`] 是**三条**：那两条管**一件**多大，
/// 本条管**一共多少件** —— 合成一个数会让「单件上限」与「目录上限」变成一件不可读的事。
pub const 缓存条目上限: usize = 256;

/// 缓存子目录名（`<运行数据根>/缓存/<本名>`）—— 固定，不随界面语言变（目录名是事实，不是文案）。
const 缓存子目录名: &str = "扩展装载";

struct 临时件清理 {
    临时路径: PathBuf,
}

impl Drop for 临时件清理 {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.临时路径);
    }
}

/// 默认缓存根目录 = `<运行数据根>/缓存/扩展装载`。
///
/// 解析不出根 ⇒ `None`（部署侧可用 `服务::缓存根` 覆盖，见 `网关.rs`）。
pub fn 默认缓存根目录() -> Option<PathBuf> {
    let 根目录 = 解析当前环境().ok()?;
    Some(子目录路径(&根目录, 子目录::缓存).join(缓存子目录名))
}

/// 缓存目录里一条**可识别的残留**（停机恢复用）：中断写入留下的临时件。
pub struct 残留项 {
    pub 路径: PathBuf,
    pub 字节数: u64,
}

/// 扫描缓存目录，识别**中断残件**（`.临时` 结尾的临时件）：停机恢复只**识别**、**不自动重放业务**，
/// 也不替调用方删（删除要人裁；正式缓存件按内容指纹定键，残件不参与取件）。
///
/// 读不到目录 ⇒ 空表（没有缓存根 = 没有残留，不是错误）。
pub fn 扫缓存残留(缓存根目录: &Path) -> Vec<残留项> {
    let Ok(读目录) = fs::read_dir(缓存根目录) else {
        return Vec::new();
    };
    let mut 残留表: Vec<残留项> = Vec::new();
    for 明细条目 in 读目录.flatten() {
        if !明细条目.file_name().to_string_lossy().ends_with(".临时") {
            continue;
        }
        let Ok(文件属性) = 明细条目.metadata() else {
            continue;
        };
        if 文件属性.is_file() {
            残留表.push(残留项 {
                路径: 明细条目.path(),
                字节数: 文件属性.len(),
            });
        }
    }
    残留表.sort_by(|前项, 后项| 前项.路径.cmp(&后项.路径));
    残留表
}

/// 读制品 → 判来源 → 校验内容 → 由内容定名 → 落缓存件 ⇒ 交回落盘路径。
///
/// 失败一律给一句可读原因（与 `取扩展声明` 同形）：扫描面上「这一个子目录不是可装载件」是
/// **正常结局**，不该中断别的子目录。
///
/// **本函数只编排、不代判**：四件事各有各的落点（[`判定来源信任`] · [`校验内容`] ·
/// [`由内容算`] · [`写入缓存件`]），顺序即依赖 —— 来源不可信就不必读字节，
/// 内容不合格就不必算名，名算出来才谈落点。
pub fn 解包到缓存(制品路径: &Path, 缓存根目录: &Path) -> Result<PathBuf, String> {
    解包到缓存择源(&[制品路径], 缓存根目录)
}

/// **候选来源多路解析** —— 同一份制品可能从多条来源路径取得到，逐条判「信不信得过」，
/// 取**第一条可信**的。
///
/// **为什么要多路**（架构收敛方案 B09 的「候选路径」那一项）：运行期重扫与跨进程装配两条路
/// 各按那一侧的形状给路径（相对仓根 / 扩展落点目录）；把「到底去哪取」交给**单一硬编码**
/// 路径就等于把两路的约定混成一个。
///
/// **全不可信时把每条的拒因一并报出**：只报「都不行」的话，调用方无从知道是路径写错了还是
/// 权限不对（与「失败必须立刻可见」同一条）。**不挑「第一条存在」的** —— 来源可信与存在
/// 是两件事（符号链接也「存在」）。
pub fn 按候选择源<'来源>(候选来源表: &[&'来源 Path]) -> Result<&'来源 Path, String> {
    if 候选来源表.is_empty() {
        return Err("候选来源表是空的（连一条可取的路径都没有）".to_owned());
    }
    let mut 候选明细: Vec<String> = Vec::new();
    for 候选路径 in 候选来源表 {
        match 判定来源信任(候选路径) {
            Ok(()) => return Ok(候选路径),
            Err(拒因) => 候选明细.push(format!("{}：{拒因}", 候选路径.display())),
        }
    }
    Err(format!("{} 条候选全都不可信：{}", 候选来源表.len(), 候选明细.join(" · ")))
}

/// [`解包到缓存`] 的多来源版：先按候选择源，再走同一条单来源链。
pub fn 解包到缓存择源(候选来源表: &[&Path], 缓存根目录: &Path) -> Result<PathBuf, String> {
    let 选中来源 = 按候选择源(候选来源表)?;
    let 制品字节 = 读制品有上限(选中来源, 能力码字节上限)?;
    let 能力码段 = 校验内容(&制品字节)?;
    let 键名 = 由内容算(&能力码段);
    判缓存预算(缓存根目录, 能力码段.len() as u64)?;
    写入缓存件(缓存根目录, &键名, &能力码段)
}

/// **来源信任** —— 只回答「这条**来源**路径信不信得过」。
///
/// **不看内容、不看落点**：来源链上的符号链接或非普通文件一律不信任 —— 符号链接的所指
/// 可以在「校验」与「落盘」之间被换掉，那两处校验过的就不是同一份字节。
fn 判定来源信任(制品路径: &Path) -> Result<(), String> {
    let 来源属性 =
        fs::symlink_metadata(制品路径).map_err(|错误| format!("读不到制品：{错误}"))?;
    if 来源属性.file_type().is_symlink() || !来源属性.is_file() {
        return Err("制品来源是符号链接或非普通文件".to_owned());
    }
    Ok(())
}

/// **内容校验** —— 只回答「这串字节是不是它自称的那个能力包件」，过则交出其中的能力码段。
///
/// **不看路径、不看落点**：同一串字节无论从哪读来，判定都一样（判据只挂在内容上）。
fn 校验内容(制品字节: &[u8]) -> Result<Vec<u8>, String> {
    let 三段 = 容器::解包(制品字节).map_err(|错误| format!("不是能力包件：{错误:?}"))?;
    if 容器::校验段指纹(制品字节) != Some(true) {
        return Err("制品段指纹缺失、损坏或与内容不符".to_owned());
    }
    let 本体段头 = 容器::文件头魔数.len() + 容器::段头长度 + 三段.接口说明段.len();
    if 制品字节.get(本体段头 + 0x0B) != Some(&容器::段类型_能力码)
        || 三段.能力码段.is_empty()
    {
        return Err("本体不是非空的支持库能力码段，不进 dlopen".to_owned());
    }
    Ok(三段.能力码段)
}

/// **读制品有上限** —— 先看元数据字节数，过了上限就不读（**不是先读进来再判**）。
///
/// 元数据读不到 ⇒ 如实报因（不当作「大小 0」放过）。
fn 读制品有上限(制品路径: &Path, 字节上限: u64) -> Result<Vec<u8>, String> {
    let 制品属性 = fs::metadata(制品路径).map_err(|错误| format!("读不到制品：{错误}"))?;
    if 制品属性.len() > 字节上限 {
        return Err(format!(
            "制品 {} 字节，超过上限 {} 字节 ⇒ 不读进内存（要先裁上界才能装）",
            制品属性.len(),
            字节上限
        ));
    }
    fs::read(制品路径).map_err(|错误| format!("读不到制品：{错误}"))
}

/// **由内容算** —— 缓存件的**名**只由内容定（`内容 → 名`，来源与落点都不参与）。
///
/// 同一个能力码段，从哪读来、往哪落，算出来的名都一样
/// （`完整落盘重入及内容定键` 钉住这一条）。
fn 由内容算(能力码段: &[u8]) -> String {
    容器::算指纹(能力码段)
        .iter().map(|字节| format!("{字节:02x}")).collect()
}

/// **路径对象** —— 只回答「这条**落点**路径链能不能落」。
///
/// **不看内容、不看来源**：链上每一段要么还不存在（可以建），要么是**真目录**且不是符号链接。
/// 判的是路径链这个对象，与要落的字节是什么无关。
fn 缓存路径对象(缓存根目录: &Path) -> Result<(), String> {
    for 目录路径 in 缓存根目录.ancestors() {
        if 目录路径.as_os_str().is_empty() {
            continue;
        }
        match fs::symlink_metadata(目录路径) {
            Ok(目录属性) if 目录属性.is_dir() && !目录属性.file_type().is_symlink() => {}
            Ok(_) => return Err(format!("缓存目录链含符号链接或非目录：{}", 目录路径.display())),
            Err(错误) if 错误.kind() == std::io::ErrorKind::NotFound => {}
            Err(错误) => return Err(format!("缓存目录检查失败：{错误}")),
        }
    }
    Ok(())
}

/// **缓存写入** —— 只回答「把这段字节**落到这条路径**上」，且可重入。
///
/// **不判来源**（来源已由 [`判定来源信任`] 判过）、**不重判内容**（内容已由 [`校验内容`] 判过，
/// 字节由调用方交进来）：写临时件 → `hard_link` 原子发布（同名已在即视为已写好）→ 复核落盘件。
// ── 子模块：预算判据（落盘前的两条上限：磁盘预算 · 缓存条目上限）──
//
// 拆出的理由：单源 ≤ 800 行。拆法按**关注点** —— 父件管「从盘上取一份字节」
// （来源 / 内容 / 名 / 写），子件管「这份字节准不准落盘」。
#[path = "装载件缓存/预算判据.rs"]
mod 预算判据;
use 预算判据::判缓存预算;

fn 写入缓存件(缓存根目录: &Path, 键名: &str, 能力码段: &[u8]) -> Result<PathBuf, String> {
    缓存路径对象(缓存根目录)?;
    fs::create_dir_all(缓存根目录).map_err(|错误| format!("建不出缓存目录：{错误}"))?;
    缓存路径对象(缓存根目录)?;
    let 落盘路径 = 缓存根目录.join(键名);
    if 验证缓存件(&落盘路径, 能力码段)? {
        return Ok(落盘路径);
    }
    let (临时清理, mut 临时文件) = 创建缓存临时件(缓存根目录, 键名)?;
    临时文件.write_all(能力码段)
        .and_then(|_| 临时文件.sync_all())
        .map_err(|错误| format!("缓存临时件写入或同步失败：{错误}"))?;
    drop(临时文件);
    缓存路径对象(缓存根目录)?;
    match fs::hard_link(&临时清理.临时路径, &落盘路径) {
        Ok(()) => {}
        Err(错误) if 错误.kind() == std::io::ErrorKind::AlreadyExists => {}
        Err(错误) => return Err(format!("缓存原子发布失败：{错误}")),
    }
    if !验证缓存件(&落盘路径, 能力码段)? {
        return Err("发布后的缓存件不存在".to_owned());
    }
    Ok(落盘路径)
}

fn 验证缓存件(落盘路径: &Path, 能力码段: &[u8]) -> Result<bool, String> {
    let 缓存属性 = match fs::symlink_metadata(落盘路径) {
        Ok(缓存属性) => 缓存属性,
        Err(错误) if 错误.kind() == std::io::ErrorKind::NotFound => return Ok(false),
        Err(错误) => return Err(format!("缓存件检查失败：{错误}")),
    };
    if !缓存属性.is_file() || 缓存属性.file_type().is_symlink() {
        return Err("缓存目标是符号链接或非普通文件".to_owned());
    }
    // **权限位**：缓存件不许组/他人可写（`0o022` 位不为零即拒）。
    //
    // **为什么**：缓存件是 `dlopen` 的对象，而校验（指纹 / 长度 / 字节比对）与 `dlopen` 不是
    // 同一个瞬间 —— 别人能在中间改它，那校验过的就不是同一份字节（与「来源是符号链接即拒」
    // 同一条理由：**校验的对象必须是不可被第三方替换的那个东西**）。只在 unix 上判。
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let 模式位 = 缓存属性.permissions().mode();
        if 模式位 & 0o022 != 0 {
            return Err(format!(
                "缓存件权限位过宽：{} 的模式位是 {模式位:o}（组或他人可写）⇒ 拒",
                落盘路径.display()
            ));
        }
    }
    if 缓存属性.len() != 能力码段.len() as u64 {
        return Err("已有缓存件长度与能力码不符".to_owned());
    }
    let mut 打开选项 = fs::OpenOptions::new();
    打开选项.read(true);
    #[cfg(any(target_os = "linux", target_os = "android"))]
    {
        use std::os::unix::fs::OpenOptionsExt;
        打开选项.custom_flags(0x20000);
    }
    #[cfg(target_vendor = "apple")]
    {
        use std::os::unix::fs::OpenOptionsExt;
        打开选项.custom_flags(0x100);
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        打开选项.custom_flags(0x00200000);
    }
    let 缓存文件 = 打开选项.open(落盘路径)
        .map_err(|错误| format!("缓存件打开失败：{错误}"))?;
    let 打开属性 = 缓存文件.metadata().map_err(|错误| format!("缓存句柄检查失败：{错误}"))?;
    if !打开属性.is_file() {
        return Err("缓存句柄不是普通文件".to_owned());
    }
    let mut 缓存字节 = Vec::new();
    缓存文件.take(能力码段.len() as u64 + 1).read_to_end(&mut 缓存字节)
        .map_err(|错误| format!("缓存件读取失败：{错误}"))?;
    let 复核属性 = fs::symlink_metadata(落盘路径)
        .map_err(|错误| format!("缓存件复核失败：{错误}"))?;
    if !复核属性.is_file() || 复核属性.file_type().is_symlink() || 缓存字节 != 能力码段 {
        return Err("已有缓存件内容不符或目标被替换".to_owned());
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if 打开属性.dev() != 复核属性.dev() || 打开属性.ino() != 复核属性.ino() {
            return Err("缓存件读取期间目标被替换".to_owned());
        }
    }
    Ok(true)
}

fn 创建缓存临时件(缓存根目录: &Path, 键名: &str) -> Result<(临时件清理, fs::File), String> {
    let 时间戳 = SystemTime::now().duration_since(UNIX_EPOCH)
        .map_err(|错误| format!("临时件时钟读取失败：{错误}"))?.as_nanos();
    for 临时序号 in 0..128 {
        let 临时路径 = 缓存根目录.join(format!(
            ".{键名}.{}.{时间戳}.{临时序号}.临时", std::process::id()
        ));
        match fs::OpenOptions::new().write(true).create_new(true).open(&临时路径) {
            Ok(临时文件) => return Ok((临时件清理 { 临时路径 }, 临时文件)),
            Err(错误) if 错误.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(错误) => return Err(format!("缓存临时件创建失败：{错误}")),
        }
    }
    Err("缓存临时件名称竞争次数超限".to_owned())
}

// ─────────────────────────────────────────────────────────────────────────────
// 三 模块本机执行体（段 `20`）：另一类本体，另一条落法
// ─────────────────────────────────────────────────────────────────────────────
//
// 支持库的本体是**能力码段**（`17`）—— 解出来就能 `dlopen`。
// 模块的本体是**本机执行体段**（`20`）—— 段里装的是 `[平台身份][执行体机器码]`
// （形状见 `v1_contract::容器::执行体载荷`）⇒ 落缓存**之前**多两件事：拆载荷、判平台身份。
//
// 判平台身份是**裁决 §三 的硬要求**：不匹配即拒、报结构化错误、**不静默降级**
// （不许「跳过执行体、只当声明用」）。故它单列一件，不与内容校验混判。

/// **执行体内容校验** —— 只回答「这串字节是不是它自称的模块制品」，过则交出**段 `20` 载荷**。
///
/// **不看路径、不看落点**（与 [`校验内容`] 同一条规矩）。
fn 校验执行体内容(制品字节: &[u8]) -> Result<Vec<u8>, String> {
    let 三段 = 容器::解包类型化(制品字节).map_err(|错误| format!("不是能力包件：{错误:?}"))?;
    if 容器::校验段指纹(制品字节) != Some(true) {
        return Err("制品段指纹缺失、损坏或与内容不符".to_owned());
    }
    if 三段.本体段类别 != 容器::本体段类别::本机执行体 {
        return Err("本体不是本机执行体段（段 20），不进 dlopen".to_owned());
    }
    Ok(三段.本体段)
}

/// **平台身份判定** —— 只回答「这段执行体是不是给这台机器的」。
///
/// 过则交出**纯执行体字节**：平台身份是**执行体的属性**，不是要落盘的字节 ⇒ 落缓存前剥掉。
/// 不匹配 ⇒ 拒（裁决 §三）。**不降级、不「先装着以后再说」**。
fn 判平台身份(载荷: &[u8], 当前平台身份: &str) -> Result<Vec<u8>, String> {
    let (制品身份, 执行体) =
        容器::拆执行体载荷(载荷).map_err(|错误| format!("执行体载荷拆不开：{错误:?}"))?;
    if 制品身份 != 当前平台身份 {
        return Err(format!("平台身份不符：制品给 {制品身份} · 本机是 {当前平台身份}"));
    }
    Ok(执行体)
}

/// 编排：模块制品 → 段 `20` 执行体落缓存（**各步各判，一个都不代另一个判**）。
///
/// 与 [`解包到缓存`] 的差别只有一条：本体是段 `20`，故中间多一步「判平台身份」。
pub fn 解包模块执行体到缓存(
    制品路径: &Path,
    缓存根目录: &Path,
    当前平台身份: &str,
) -> Result<PathBuf, String> {
    判定来源信任(制品路径)?;
    let 制品字节 = 读制品有上限(制品路径, 执行体字节上限)?;
    let 载荷 = 校验执行体内容(&制品字节)?;
    let 执行体 = 判平台身份(&载荷, 当前平台身份)?;
    let 键名 = 由内容算(&执行体);
    判缓存预算(缓存根目录, 执行体.len() as u64)?;
    写入缓存件(缓存根目录, &键名, &执行体)
}

#[cfg(test)]
mod 缓存测试 {
    use super::*;
    use std::sync::{Arc, Barrier};

    struct 测试目录 { 目录根: PathBuf }
    impl Drop for 测试目录 {
        fn drop(&mut self) { let _ = fs::remove_dir_all(&self.目录根); }
    }
    fn 创建测试目录() -> 测试目录 {
        for 临时序号 in 0..128 {
            let 时间戳 = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
            let 目录根 = std::env::temp_dir().canonicalize().unwrap()
                .join(format!("装载件缓存验证-{}-{时间戳}-{临时序号}", std::process::id()));
            match fs::create_dir(&目录根) {
                Ok(()) => return 测试目录 { 目录根 },
                Err(错误) if 错误.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(错误) => panic!("创建测试目录失败：{错误}"),
            }
        }
        panic!("测试目录竞争次数超限")
    }
    fn 写测试制品(目录根: &Path, 制品字节: &[u8]) -> PathBuf {
        let 制品文件 = 目录根.join("样例.支持库制品");
        fs::write(&制品文件, 制品字节).unwrap();
        制品文件
    }
    fn 缓存键路径(缓存目录: &Path, 代码字节: &[u8]) -> PathBuf {
        let 缓存键: String = 容器::算指纹(代码字节).iter()
            .map(|字节| format!("{字节:02x}")).collect();
        缓存目录.join(缓存键)
    }

    #[test]
    fn 指纹篡改拒绝且不产生缓存() {
        let 测试目录 = 创建测试目录();
        let 缓存目录 = 测试目录.目录根.join("缓存");
        let mut 篡改制品 = 容器::装包(b"interface", b"native-code");
        let 本体段头 = 容器::文件头魔数.len() + 容器::段头长度 + b"interface".len();
        篡改制品[本体段头 + 容器::段头长度] ^= 1;
        assert_eq!(容器::校验段指纹(&篡改制品), Some(false));
        let 制品文件 = 写测试制品(&测试目录.目录根, &篡改制品);
        assert!(解包到缓存(&制品文件, &缓存目录).is_err());
        assert!(!缓存目录.exists());
        let mut 篡改制品 = 容器::装包(b"interface", b"native-code");
        篡改制品.pop();
        let 制品文件 = 写测试制品(&测试目录.目录根, &篡改制品);
        assert!(解包到缓存(&制品文件, &缓存目录).is_err());
        assert!(!缓存目录.exists());
    }

    #[test]
    fn 本体类型及空码拒绝() {
        let 测试目录 = 创建测试目录();
        let 缓存目录 = 测试目录.目录根.join("缓存");
        let 技能制品 = 容器::装包三段(b"interface", b"skill", 容器::段类型_技能本体);
        let mut 伪装技能 = 技能制品.clone();
        let 本体段头 = 伪装技能.len() - 容器::指纹宽度 - 1;
        伪装技能[本体段头] = 容器::段类型_能力码;
        assert_eq!(容器::校验段指纹(&伪装技能), Some(false));
        let 空码制品 = 容器::装包(b"interface", b"");
        for 制品字节 in [技能制品, 伪装技能, 空码制品] {
            let 制品文件 = 写测试制品(&测试目录.目录根, &制品字节);
            assert!(解包到缓存(&制品文件, &缓存目录).is_err());
            assert!(!缓存目录.exists());
        }
    }

    #[test]
    fn 完整落盘重入及内容定键() {
        let 测试目录 = 创建测试目录();
        let 缓存目录 = 测试目录.目录根.join("缓存");
        let 代码字节 = b"native-code";
        let 目标路径 = 缓存键路径(&缓存目录, 代码字节);
        for 制品字节 in [容器::装包(b"interface", 代码字节), 容器::装包(b"changed", 代码字节)] {
            let 制品文件 = 写测试制品(&测试目录.目录根, &制品字节);
            assert_eq!(解包到缓存(&制品文件, &缓存目录).unwrap(), 目标路径);
            assert_eq!(解包到缓存(&制品文件, &缓存目录).unwrap(), 目标路径);
            assert_eq!(fs::read(&目标路径).unwrap(), 代码字节);
        }
        assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 1);
    }

    #[test]
    fn 同键并发只见完整制品() {
        let 测试目录 = 创建测试目录();
        let 缓存目录 = 测试目录.目录根.join("缓存");
        let 代码字节 = vec![0x42; 256 * 1024];
        let 制品文件 = 写测试制品(&测试目录.目录根, &容器::装包(b"interface", &代码字节));
        let 目标路径 = 缓存键路径(&缓存目录, &代码字节);
        let 并发屏障 = Arc::new(Barrier::new(9));
        let mut 线程列表 = Vec::new();
        for _ in 0..8 {
            let 线程制品 = 制品文件.clone();
            let 线程缓存 = 缓存目录.clone();
            let 线程屏障 = 并发屏障.clone();
            线程列表.push(std::thread::spawn(move || {
                线程屏障.wait();
                解包到缓存(&线程制品, &线程缓存).unwrap()
            }));
        }
        并发屏障.wait();
        while 线程列表.iter().any(|工作线程| !工作线程.is_finished()) {
            match fs::read(&目标路径) {
                Ok(缓存字节) => assert_eq!(缓存字节, 代码字节),
                Err(错误) => assert_eq!(错误.kind(), std::io::ErrorKind::NotFound),
            }
            std::thread::yield_now();
        }
        for 工作线程 in 线程列表 { assert_eq!(工作线程.join().unwrap(), 目标路径); }
        assert_eq!(fs::read(&目标路径).unwrap(), 代码字节);
        assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 1);
    }

    #[test]
    fn 损坏旧缓存及非文件拒绝() {
        let 测试目录 = 创建测试目录();
        let 缓存目录 = 测试目录.目录根.join("缓存");
        fs::create_dir(&缓存目录).unwrap();
        let 制品文件 = 写测试制品(&测试目录.目录根, &容器::装包(b"interface", b"native-code"));
        let 目标路径 = 缓存键路径(&缓存目录, b"native-code");
        for 缓存字节 in [b"broken-code".as_slice(), b"".as_slice()] {
            fs::write(&目标路径, 缓存字节).unwrap();
            assert!(解包到缓存(&制品文件, &缓存目录).is_err());
            assert_eq!(fs::read(&目标路径).unwrap(), 缓存字节);
        }
        fs::remove_file(&目标路径).unwrap();
        fs::create_dir(&目标路径).unwrap();
        assert!(解包到缓存(&制品文件, &缓存目录).is_err());
        assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 1);
    }

    #[cfg(unix)]
    #[test]
    fn 符号链接目标及目录拒绝() {
        use std::os::unix::fs::symlink;
        let 测试目录 = 创建测试目录();
        let 缓存目录 = 测试目录.目录根.join("缓存");
        fs::create_dir(&缓存目录).unwrap();
        let 制品文件 = 写测试制品(&测试目录.目录根, &容器::装包(b"interface", b"native-code"));
        let 目标路径 = 缓存键路径(&缓存目录, b"native-code");
        symlink(&制品文件, &目标路径).unwrap();
        assert!(解包到缓存(&制品文件, &缓存目录).is_err());
        fs::remove_file(&目标路径).unwrap();
        symlink(测试目录.目录根.join("不存在"), &目标路径).unwrap();
        assert!(解包到缓存(&制品文件, &缓存目录).is_err());
        fs::remove_file(&目标路径).unwrap();
        fs::remove_dir(&缓存目录).unwrap();
        symlink(&测试目录.目录根, &缓存目录).unwrap();
        assert!(解包到缓存(&制品文件, &缓存目录).is_err());
        assert!(!缓存键路径(&测试目录.目录根, b"native-code").exists());
    }

    #[test]
    fn 中断残件忽略且失败临时件清理() {
        let 测试目录 = 创建测试目录();
        let 缓存目录 = 测试目录.目录根.join("缓存");
        fs::create_dir(&缓存目录).unwrap();
        let 残件路径 = 缓存目录.join(".中断.临时");
        fs::write(&残件路径, b"partial").unwrap();
        let 制品文件 = 写测试制品(&测试目录.目录根, &容器::装包(b"interface", b"native-code"));
        let 目标路径 = 解包到缓存(&制品文件, &缓存目录).unwrap();
        assert_eq!(fs::read(&目标路径).unwrap(), b"native-code");
        assert_eq!(fs::read(&残件路径).unwrap(), b"partial");
        let (临时清理, mut 临时文件) = 创建缓存临时件(&缓存目录, "失败样例").unwrap();
        let 清理路径 = 临时清理.临时路径.clone();
        let 失败结果: std::io::Result<()> = (|| {
            let 临时清理 = 临时清理;
            临时文件.write_all(b"partial")?;
            drop(临时文件);
            fs::hard_link(&临时清理.临时路径, &缓存目录)
        })();
        assert!(失败结果.is_err());
        assert!(!清理路径.exists());
        assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 2);
    }

    /// **平台身份（段 `20`）不符即拒、且一个缓存件都不落** —— 这一条要的是**反向样本**。
    ///
    /// 正向例子只能证明「身份相符时跑得通」，证不了「不符时真会挡」；
    /// 平台身份是「这台机器 + 这个 rustc」的产物，判错就是**静默降级**（裁决 §三 明禁）。
    #[test]
    fn 平台身份不符即拒且不产缓存() {
        let 测试目录 = 创建测试目录();
        let 缓存目录 = 测试目录.目录根.join("缓存");
        let 制品身份 = "x86_64-unknown-linux-gnu";
        let 载荷 = 容器::打包执行体载荷(制品身份, b"native-code");
        let 执行体包件 = 容器::装包三段(b"interface", &载荷, 容器::段类型_本机执行体);
        let 制品文件 = 写测试制品(&测试目录.目录根, &执行体包件);

        // ① 制品给别的平台、本机是另一个 ⇒ 拒，且拒在缓存键之前 ⇒ 一个缓存件都不落。
        let 拒绝结果 = 解包模块执行体到缓存(&制品文件, &缓存目录, "aarch64-apple-darwin");
        assert!(拒绝结果.is_err(), "平台身份不符必须拒，实际放过了：{拒绝结果:?}");
        assert!(
            拒绝结果.unwrap_err().contains(制品身份),
            "拒的理由要带上制品自称的那个身份，才定位得到是哪个制品给错了平台"
        );
        assert!(
            !缓存目录.exists() || fs::read_dir(&缓存目录).unwrap().count() == 0,
            "拒之后不许留下任何缓存件"
        );

        // ② 报上制品那个身份 ⇒ 过，且落盘的是**纯执行体**（身份是执行体的属性，落盘前剥掉）。
        let 落点 = 解包模块执行体到缓存(&制品文件, &缓存目录, 制品身份)
            .expect("身份相符必须过");
        assert_eq!(fs::read(&落点).unwrap(), b"native-code", "落盘的是执行体字节，不带身份前缀");
    }

    /// 四件事各判各的、互不顶替 —— 每一面各造一个**只有它该拒**的现场：
    /// ① 内容坏而来源好；② 来源是符号链接而内容好；③ 来源与内容都好而落点链含符号链接；
    /// ④ 写入只认「字节 + 落点」这一对（同内容同落点、异内容异名）。
    #[test]
    fn 四者各判各的不互相顶替() {
        use std::os::unix::fs::symlink;
        let 测试目录 = 创建测试目录();
        let 缓存目录 = 测试目录.目录根.join("缓存");
        fs::create_dir(&缓存目录).unwrap();
        let 好制品 = 容器::装包(b"interface", b"native-code");

        // ① 内容校验拒 · 来源信任放行 ⇒ 一个缓存件都不该落下。
        let mut 坏字节 = 好制品.clone();
        坏字节.pop();
        assert!(校验内容(&坏字节).is_err());
        let 坏制品文件 = 写测试制品(&测试目录.目录根, &坏字节);
        assert!(判定来源信任(&坏制品文件).is_ok());
        assert!(解包到缓存(&坏制品文件, &缓存目录).is_err());
        assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 0);

        // ② 来源信任拒 · 内容校验放行 ⇒ 链接指到的是真制品，照样不落。
        let 好制品文件 = 写测试制品(&测试目录.目录根, &好制品);
        assert!(校验内容(&fs::read(&好制品文件).unwrap()).is_ok());
        let 链接制品 = 测试目录.目录根.join("链接制品.支持库制品");
        symlink(&好制品文件, &链接制品).unwrap();
        assert!(判定来源信任(&链接制品).is_err());
        assert!(解包到缓存(&链接制品, &缓存目录).is_err());
        assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 0);

        // ③ 路径对象拒 · 来源与内容都放行 ⇒ 拒的是落点链，不是制品。
        let 链接缓存 = 测试目录.目录根.join("链接缓存");
        symlink(&缓存目录, &链接缓存).unwrap();
        assert!(缓存路径对象(&链接缓存).is_err());
        assert!(判定来源信任(&好制品文件).is_ok());
        assert!(解包到缓存(&好制品文件, &链接缓存).is_err());

        // ④ 写入只认「字节 + 落点」：名由内容定 ⇒ 同内容重入落同一件、异内容异名。
        let 首次落点 = 写入缓存件(&缓存目录, &由内容算(b"native-code"), b"native-code").unwrap();
        assert_eq!(fs::read(&首次落点).unwrap(), b"native-code");
        let 重算落点 = 写入缓存件(&缓存目录, &由内容算(b"native-code"), b"native-code").unwrap();
        assert_eq!(重算落点, 首次落点);
        let 异内容落点 = 缓存目录.join(由内容算(b"other-code"));
        assert_ne!(异内容落点, 首次落点);
        assert_eq!(fs::read_dir(&缓存目录).unwrap().count(), 1);
    }
}
/// 单测：候选择源 / 读制品有上限 / 权限位过宽 三条反向样本。
#[cfg(test)]
mod 加固测试 {
    use super::*;

    struct 临时目录 {
        目录根: PathBuf,
    }
    impl Drop for 临时目录 {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.目录根);
        }
    }
    fn 建临时目录(标签: &str) -> 临时目录 {
        for 临时序号 in 0..128 {
            let 时间戳 = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
            let 目录根 = std::env::temp_dir()
                .canonicalize()
                .unwrap()
                .join(format!("装载件缓存加固-{标签}-{}-{时间戳}-{临时序号}", std::process::id()));
            match fs::create_dir(&目录根) {
                Ok(()) => return 临时目录 { 目录根 },
                Err(错误) if 错误.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(错误) => panic!("创建测试目录失败：{错误}"),
            }
        }
        panic!("测试目录竞争次数超限")
    }
    fn 写制品(目录根: &Path) -> (PathBuf, &'static [u8]) {
        let 代码字节: &'static [u8] = b"native-code";
        let 制品文件 = 目录根.join("样例.支持库制品");
        fs::write(&制品文件, 容器::装包(b"interface", 代码字节)).unwrap();
        (制品文件, 代码字节)
    }

    /// 候选择源：符号链接那一条跳过、真件那一条选中；全不可信时逐条报出拒因。
    #[test]
    fn 候选择源_全不可信时报出每一条拒因() {
        let 测试根 = 建临时目录("择源");
        let (真件, _) = 写制品(&测试根.目录根);
        let 全假件 = 测试根.目录根.join("假制品.支持库制品");
        assert_eq!(按候选择源(&[&全假件, &真件]).unwrap(), 真件.as_path(), "链件不参与时选中真件");
        #[cfg(unix)]
        {
            let 链件 = 测试根.目录根.join("链制品.支持库制品");
            std::os::unix::fs::symlink(&真件, &链件).unwrap();
            assert_eq!(按候选择源(&[&链件, &真件]).unwrap(), 真件.as_path(), "链件跳过、真件选中");
        }
        let 全不可信 = 按候选择源(&[&全假件]).unwrap_err();
        assert!(全不可信.contains("假制品"), "拒因要点名那一条路径：{全不可信}");
        assert!(按候选择源(&[]).unwrap_err().contains("空的"));
    }

    /// 读制品有上限：**先看元数据、过线就不读** —— 超限报因、未超限原样读回。
    #[test]
    fn 读制品有上限_超限不读未超限读回() {
        let 测试根 = 建临时目录("大小");
        let (制品文件, 代码字节) = 写制品(&测试根.目录根);
        let 超过本件长度 = 容器::装包(b"interface", 代码字节).len() as u64 - 1;
        let 拒因 = 读制品有上限(&制品文件, 超过本件长度).unwrap_err();
        assert!(拒因.contains("超过上限"), "该报超上限：{拒因}");
        assert_eq!(读制品有上限(&制品文件, 能力码字节上限).unwrap().len() as u64, 超过本件长度 + 1);
    }

    /// 权限位过宽：组/他人可写的缓存件 ⇒ 拒（校验过的字节可能被第三方换掉）。
    #[cfg(unix)]
    #[test]
    fn 权限位过宽即拒() {
        use std::os::unix::fs::PermissionsExt;
        let 测试根 = 建临时目录("权限");
        let 缓存目录 = 测试根.目录根.join("缓存");
        let (制品文件, _) = 写制品(&测试根.目录根);
        let 落点 = 解包到缓存(&制品文件, &缓存目录).unwrap();
        let mut 权限 = fs::metadata(&落点).unwrap().permissions();
        权限.set_mode(0o666);
        fs::set_permissions(&落点, 权限).unwrap();
        let 拒因 = 解包到缓存(&制品文件, &缓存目录).unwrap_err();
        assert!(拒因.contains("权限位过宽"), "该报权限位过宽：{拒因}");
    }
}
