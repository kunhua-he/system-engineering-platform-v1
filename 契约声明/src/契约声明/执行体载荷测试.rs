use super::*;

#[test]
fn 打包拆包往返一致() {
    let 载荷 = 打包执行体载荷("aarch64-apple-darwin", b"\xcf\xfa\xed\xfeMODULE");
    let (身份, 执行体) = 拆执行体载荷(&载荷).unwrap();
    assert_eq!(身份, "aarch64-apple-darwin");
    assert_eq!(执行体, b"\xcf\xfa\xed\xfeMODULE");
}

#[test]
fn 截断与空执行体各报各的() {
    assert_eq!(拆执行体载荷(&[]), Err(载荷错误::载荷截断));
    assert_eq!(拆执行体载荷(&[0, 0]), Err(载荷错误::执行体为空));
    assert_eq!(
        拆执行体载荷(&[0, 3, b'a']),
        Err(载荷错误::身份长度越界 { 声明: 3, 可读: 3 })
    );
}

#[test]
fn 身份非文本与超上界拒绝() {
    assert_eq!(拆执行体载荷(&[0, 1, 0xff, 1]), Err(载荷错误::身份非文本));
    let 超界 = (身份长度上界 as u16 + 1).to_be_bytes();
    assert_eq!(
        拆执行体载荷(&[超界[0], 超界[1], 1]),
        Err(载荷错误::身份长度越界 { 声明: 身份长度上界 + 1, 可读: 3 })
    );
}

#[test]
fn 上界内最长身份仍往返() {
    let 长身份 = "x".repeat(身份长度上界);
    let 载荷 = 打包执行体载荷(&长身份, b"K");
    let (身份, 执行体) = 拆执行体载荷(&载荷).unwrap();
    assert_eq!(身份, 长身份);
    assert_eq!(执行体, b"K");
}
