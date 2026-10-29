#[test]
fn 测试登录失败次数边界(){
    assert_eq!(super::登录判定面::判登录次数(0,5),Ok(false));
    assert_eq!(super::登录判定面::判登录次数(4,5),Ok(false));
    assert_eq!(super::登录判定面::判登录次数(5,5),Ok(true));
    assert_eq!(super::登录判定面::判登录次数(6,5),Ok(true));
    assert!(super::登录判定面::判登录次数(-1,5).is_err());
    assert!(super::登录判定面::判登录次数(0,0).is_err());
}
