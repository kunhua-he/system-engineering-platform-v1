use std::io::Write;
use std::process::{Command, Stdio};

#[test]
fn 整页宿主请求与信封执行验证() {
    for 操作地址 in ["", "/转发?说明='引号&内容=</script>"] {
        let 树定义原文 = serde_json::json!({"整页":true,"组件操作地址":操作地址,"根":{"类型":"表格","列":["销量"],"行":[[20],[10]],"可排序":true}}).to_string();
        let (_, 页面字节) = super::渲染组件树(&树定义原文).unwrap();
        let mut 验证进程 = Command::new("node")
            .arg("-e")
            .arg(include_str!("宿主合同测试.js"))
            .arg(if 操作地址.is_empty() {
                "/接口/调用"
            } else {
                操作地址
            })
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .expect("执行宿主合同测试需要 node");
        验证进程.stdin.take().unwrap().write_all(&页面字节).unwrap();
        let 验证回执 = 验证进程.wait_with_output().unwrap();
        assert!(
            验证回执.status.success(),
            "{}{}",
            String::from_utf8_lossy(&验证回执.stdout),
            String::from_utf8_lossy(&验证回执.stderr)
        );
    }
}
