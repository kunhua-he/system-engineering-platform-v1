use super::*;
use core::sync::atomic::{AtomicUsize, Ordering};

static 首样本串: &[u8] = b"AAAA1111\0";
static 次样本串: &[u8] = b"BBBB2222\0";
static 末样本串: &[u8] = b"CCCC3333\0";

fn 首样本() -> *const u8 {
    首样本串.as_ptr()
}
fn 次样本() -> *const u8 {
    次样本串.as_ptr()
}
fn 末样本() -> *const u8 {
    末样本串.as_ptr()
}

/// 计数端点：把 `参数一` 当 `*const AtomicUsize`，被调一次加一，一律回成功。
/// 这样每个测试用自身局部的计数器，不需要进程级全局。
unsafe extern "C" fn 计数端点(
    _通知号: v1_contract::通知号,
    参数一: usize,
    参数二: usize,
) -> isize {
    let _ = 参数二;
    if 参数一 != 0 {
        // SAFETY: 调用方按约定把 `参数一` 传成有效的 `*const AtomicUsize`。
        let 计数 = unsafe { &*(参数一 as *const AtomicUsize) };
        计数.fetch_add(1, Ordering::SeqCst);
    }
    通知返回::成功
}

/// 收到卸载请求一律回「延迟释放」：模拟引用未清零时拒绝卸载。
unsafe extern "C" fn 延迟释放端点(
    通知号: v1_contract::通知号,
    _参数一: usize,
    _参数二: usize,
) -> isize {
    if 通知号 == 生命周期通知::卸载 {
        通知返回::延迟释放
    } else {
        通知返回::成功
    }
}

/// 收到卸载请求一律回「失败」：模拟卸载期出错。
unsafe extern "C" fn 卸载失败端点(
    通知号: v1_contract::通知号,
    _参数一: usize,
    _参数二: usize,
) -> isize {
    if 通知号 == 生命周期通知::卸载 {
        通知返回::失败
    } else {
        通知返回::成功
    }
}

/// 协商端点的「引用清零」开关：0 = 还有引用（拒绝卸载），1 = 已清零（放行）。
static 协商_引用清零: AtomicUsize = AtomicUsize::new(0);

/// 引用清零前，对 `2001 卸载` 与 `2003 延迟释放` **都**回「延迟释放」；清零后回成功。
/// 这是 ⑥ 的样本：区分「初次请求」与「引用清零后的复核」两个通知号。
unsafe extern "C" fn 协商端点(
    通知号: v1_contract::通知号,
    _参数一: usize,
    _参数二: usize,
) -> isize {
    if matches!(通知号, 生命周期通知::卸载 | 生命周期通知::延迟释放)
        && 协商_引用清零.load(Ordering::SeqCst) == 0
    {
        通知返回::延迟释放
    } else {
        通知返回::成功
    }
}

/// 计数器的地址，当作下行派发的 `参数一` 传下去。
fn 计数参数(计数: &AtomicUsize) -> usize {
    计数 as *const AtomicUsize as usize
}

#[test]
fn 正常派发() {
    let mut 通道 = 通知通道::新建();
    let 计数 = AtomicUsize::new(0);
    通道.注册(首样本(), 计数端点);

    assert_eq!(通道.端点数(), 1);
    // 段首号
    assert_eq!(
        unsafe { 通道.下行派发(v1_contract::通知号::新(通知号段::下行起), 计数参数(&计数), 0) },
        派发结果::成功
    );
    // 段末号
    assert_eq!(
        unsafe { 通道.下行派发(v1_contract::通知号::新(通知号段::下行止), 计数参数(&计数), 0) },
        派发结果::成功
    );
    assert_eq!(计数.load(Ordering::SeqCst), 2);
}

#[test]
fn 未命中() {
    let mut 通道 = 通知通道::新建();
    // 号不在下行段里：0 · 上行段 · 生命周期段 · 段外
    for 通知号 in [0u32, 1000, 1999, 2000, 2999, 3000, u32::MAX] {
        assert_eq!(
            unsafe { 通道.下行派发(v1_contract::通知号::新(通知号), 0, 0) },
            派发结果::未命中,
            "号 {通知号} 不在下行段，应为未命中"
        );
    }
    // 号在下行段里，但没有接收方 ⇒ 同样是未命中，不是失败
    assert_eq!(
        unsafe { 通道.下行派发(v1_contract::通知号::新(通知号段::下行起), 0, 0) },
        派发结果::未命中
    );
    // 注册之后同一个号就命中
    通道.注册(首样本(), 计数端点);
    assert_eq!(
        unsafe { 通道.下行派发(v1_contract::通知号::新(通知号段::下行起), 0, 0) },
        派发结果::成功
    );
    // 未注册的标识串请求卸载 ⇒ 未命中
    assert_eq!(通道.请求卸载(次样本()), 派发结果::未命中);
}

#[test]
fn 延迟释放() {
    let mut 通道 = 通知通道::新建();
    通道.注册(首样本(), 延迟释放端点);

    // 扩展请求延迟释放 ⇒ 允许被拒绝
    assert_eq!(通道.请求卸载(首样本()), 派发结果::请求延迟释放);
    // 被拒绝的卸载必须原样保留：端点还在表里
    assert_eq!(通道.端点数(), 1);
    // 再来一次仍然拒绝 —— 证明它确实还在，没被摘掉
    assert_eq!(通道.请求卸载(首样本()), 派发结果::请求延迟释放);
    assert_eq!(通道.端点数(), 1);

    // 卸载回失败 ⇒ fail-closed：不放行，端点同样放回
    通道.注册(次样本(), 卸载失败端点);
    assert_eq!(通道.请求卸载(次样本()), 派发结果::失败);
    assert_eq!(通道.端点数(), 2);

    // 引用清零后回成功 ⇒ 收回：已注册的通知被摘掉
    let 计数 = AtomicUsize::new(0);
    通道.注册(末样本(), 计数端点);
    assert_eq!(通道.端点数(), 3);
    assert_eq!(通道.请求卸载(末样本()), 派发结果::成功);
    assert_eq!(通道.端点数(), 2);
    // 末个（唯一的计数端点）已被收回 ⇒ 剩下的首个、次个照常收到号，但计数器不动
    assert_eq!(
        unsafe { 通道.下行派发(v1_contract::通知号::新(通知号段::下行起), 计数参数(&计数), 0) },
        派发结果::成功
    );
    assert_eq!(计数.load(Ordering::SeqCst), 0);
}

#[test]
fn 延迟释放协商_引用清零后再问才收回() {
    // ⑥ 的通道侧：第一次问（2001）被拒 → 引用清零前再问（2003）仍被拒 → 清零后再问才收回。
    协商_引用清零.store(0, Ordering::SeqCst);
    let mut 通道 = 通知通道::新建();
    通道.注册(首样本(), 协商端点);

    assert_eq!(通道.请求卸载(首样本()), 派发结果::请求延迟释放);
    assert_eq!(通道.端点数(), 1, "被拒的卸载必须原样保留端点");
    assert_eq!(通道.延迟释放协商(首样本()), 派发结果::请求延迟释放);
    assert_eq!(通道.端点数(), 1, "引用未清零，复核仍须拒绝");

    协商_引用清零.store(1, Ordering::SeqCst);
    assert_eq!(通道.延迟释放协商(首样本()), 派发结果::成功);
    assert_eq!(通道.端点数(), 0, "放行即收回：端点摘掉");
    // 已收回 ⇒ 再问是未命中（不是错误）。
    assert_eq!(通道.延迟释放协商(首样本()), 派发结果::未命中);
}

#[test]
fn 注销后不再派发() {
    let mut 通道 = 通知通道::新建();
    let 计数 = AtomicUsize::new(0);
    通道.注册(首样本(), 计数端点);
    通道.注册(次样本(), 计数端点);
    assert_eq!(通道.端点数(), 2);

    // 两个端点都被派发到
    assert_eq!(
        unsafe { 通道.下行派发(v1_contract::通知号::新(通知号段::下行起), 计数参数(&计数), 0) },
        派发结果::成功
    );
    assert_eq!(计数.load(Ordering::SeqCst), 2);

    通道.注销(首样本());
    assert_eq!(通道.端点数(), 1);
    // 首个不再被派发，次个照旧：只加一
    assert_eq!(
        unsafe { 通道.下行派发(v1_contract::通知号::新(通知号段::下行起), 计数参数(&计数), 0) },
        派发结果::成功
    );
    assert_eq!(计数.load(Ordering::SeqCst), 3);

    通道.注销(次样本());
    assert_eq!(通道.端点数(), 0);
    // 表空了：这个号没有接收方 ⇒ 未命中，计数不动
    assert_eq!(
        unsafe { 通道.下行派发(v1_contract::通知号::新(通知号段::下行起), 计数参数(&计数), 0) },
        派发结果::未命中
    );
    assert_eq!(计数.load(Ordering::SeqCst), 3);
}

#[test]
fn 重复注册() {
    let mut 通道 = 通知通道::新建();
    let 计数 = AtomicUsize::new(0);

    // 先注册「延迟释放端点」，再拿同一标识串注册「计数端点」——必须被拒
    通道.注册(首样本(), 延迟释放端点);
    通道.注册(首样本(), 计数端点);
    assert_eq!(通道.端点数(), 1);

    // 派发只到先注册的那个：计数端点没进表，计数器不动
    assert_eq!(
        unsafe { 通道.下行派发(v1_contract::通知号::新(通知号段::下行起), 计数参数(&计数), 0) },
        派发结果::成功
    );
    assert_eq!(计数.load(Ordering::SeqCst), 0);

    // 表里是先注册的那个：卸载仍走「延迟释放」
    assert_eq!(通道.请求卸载(首样本()), 派发结果::请求延迟释放);
    assert_eq!(通道.端点数(), 1);
}

#[test]
fn 空标识串被忽略() {
    let mut 通道 = 通知通道::新建();
    通道.注册(core::ptr::null(), 计数端点);
    assert_eq!(通道.端点数(), 0);

    通道.注册(首样本(), 计数端点);
    通道.注销(core::ptr::null()); // 空指针注销：无操作，不许误删别人
    assert_eq!(通道.端点数(), 1);
    assert_eq!(通道.请求卸载(core::ptr::null()), 派发结果::未命中);
}
