use super::*;
use std::io::{Read, Write};
use std::net::TcpListener;
use std::sync::mpsc;

fn 登记轻量进程(监听端口: u16) -> u64 {
    let 子进程 = Command::new("/bin/sleep").arg("60").spawn().unwrap();
    let 句柄 = 下一句柄.fetch_add(1, Ordering::AcqRel);
    服务表().lock().unwrap().insert(句柄, 服务条目 {
        模型短名: "释放验证".into(), 模型路径: String::new(),
        进程号: 子进程.id(), 监听端口, 模型类型: "LLM文本模型".into(),
        就绪路径: "/health".into(), 启动时刻: Instant::now(),
        最后使用时刻: Instant::now(), 闲置超时秒: 0, 载入超时秒: 0,
        已就绪: false, 子进程,
    });
    句柄
}

#[test]
fn 状态探测不占全表锁() {
    let 监听器 = TcpListener::bind("127.0.0.1:0").unwrap();
    let 句柄 = 登记轻量进程(监听器.local_addr().unwrap().port());
    let (到达发送, 到达接收) = mpsc::channel();
    let (放行发送, 放行接收) = mpsc::channel();
    let 服务线程 = std::thread::spawn(move || {
        for 连接结果 in 监听器.incoming() {
            let mut 连接流 = 连接结果.unwrap();
            连接流.set_read_timeout(Some(Duration::from_secs(2))).unwrap();
            let mut 请求缓冲 = [0; 128];
            if 连接流.read(&mut 请求缓冲).unwrap_or(0) == 0 { continue; }
            到达发送.send(()).unwrap();
            let _ = 放行接收.recv_timeout(Duration::from_secs(3));
            let _ = 连接流.write_all(b"HTTP/1.0 200 OK\r\n\r\n");
            break;
        }
    });
    let 状态线程 = std::thread::spawn(move || 取状态(句柄));
    到达接收.recv_timeout(Duration::from_secs(3)).unwrap();
    let (释放完成发送, 释放完成接收) = mpsc::channel();
    let 释放探测线程 = std::thread::spawn(move || {
        释放完成发送.send(释放(句柄, true)).unwrap();
    });
    // 健康响应尚未放行，释放应可完成；不以一次 try_lock 猜是哪条线程持锁。
    let 释放回执 = 释放完成接收.recv_timeout(Duration::from_secs(2));
    放行发送.send(()).unwrap();
    服务线程.join().unwrap();
    状态线程.join().unwrap().unwrap();
    释放探测线程.join().unwrap();
    assert_eq!(释放回执, Ok(Ok(true)), "健康请求未放行时释放仍被阻塞");
}

#[test]
fn 强制释放拒绝错配归属() {
    let 句柄 = 登记轻量进程(0);
    let mut 旁观进程 = Command::new("/bin/sleep").arg("60").spawn().unwrap();
    let 归属进程号 = {
        let mut 服务记录表 = 服务表().lock().unwrap();
        let 条目 = 服务记录表.get_mut(&句柄).unwrap();
        let 归属进程号 = 条目.进程号;
        条目.进程号 = 旁观进程.id();
        归属进程号
    };
    let 释放结果 = 释放(句柄, true);
    let 记录保留 = 服务存在(句柄);
    let 旁观存活 = 旁观进程.try_wait().unwrap().is_none();
    if let Some(条目) = 服务表().lock().unwrap().get_mut(&句柄) {
        条目.进程号 = 归属进程号;
    }
    let _ = 释放(句柄, true);
    let _ = 旁观进程.kill();
    let _ = 旁观进程.wait();
    assert_eq!(释放结果, Err(错误码::服务无效));
    assert!(记录保留 && 旁观存活);
}

#[test]
fn 等待出错不可伪造回收() {
    unsafe extern "C" { fn waitpid(进程号: i32, 状态指针: *mut i32, 等待选项: i32) -> i32; }
    let 句柄 = 登记轻量进程(0);
    {
        let mut 服务记录表 = 服务表().lock().unwrap();
        let 条目 = 服务记录表.get_mut(&句柄).unwrap();
        条目.子进程.kill().unwrap();
        let mut 状态码 = 0;
        assert_eq!(unsafe { waitpid(条目.进程号 as i32, &mut 状态码, 0) }, 条目.进程号 as i32);
    }
    let 释放结果 = 释放(句柄, true);
    let 记录保留 = 服务存在(句柄);
    服务表().lock().unwrap().remove(&句柄);
    assert_eq!(释放结果, Err(错误码::资源受限));
    assert!(记录保留, "无法确认退出时必须保留归属记录");
}

#[test]
fn 强制释放确认退出并保留旁观进程() {
    let 句柄 = 登记轻量进程(0);
    let mut 旁观进程 = Command::new("/bin/sleep").arg("60").spawn().unwrap();
    let 进程号 = 服务表().lock().unwrap().get(&句柄).unwrap().进程号;
    assert_eq!(释放(句柄, true), Ok(true));
    assert!(!服务存在(句柄));
    let 进程已退出 = !Command::new("/bin/ps").args(["-p", &进程号.to_string()]).stdout(Stdio::null()).status().unwrap().success();
    let 旁观存活 = 旁观进程.try_wait().unwrap().is_none();
    旁观进程.kill().unwrap();
    旁观进程.wait().unwrap();
    assert!(进程已退出 && 旁观存活);
    assert_eq!(释放(句柄, true), Ok(true));
}

#[test]
fn 持许可不阻塞常规释放() {
    let 句柄 = 登记轻量进程(0);
    let 许可编号 = crate::推理许可::申请(句柄, 0, 1000).unwrap();
    let 释放结果 = 释放(句柄, false);
    let 归还结果 = crate::推理许可::归还(许可编号);
    assert_eq!(释放结果, Ok(true));
    assert_eq!(归还结果, Ok(true));
    assert!(!服务存在(句柄));
}

#[test]
fn 忽略温和信号仍能并发强制释放() {
    use std::io::BufRead;
    let 句柄 = 登记轻量进程(0);
    let mut 抗终止进程 = Command::new("/bin/sh")
        .args(["-c", "trap '' TERM; printf 'ready\n'; exec /bin/sleep 60"])
        .stdout(Stdio::piped()).spawn().unwrap();
    let mut 就绪文本 = String::new();
    std::io::BufReader::new(抗终止进程.stdout.take().unwrap()).read_line(&mut 就绪文本).unwrap();
    let 进程号 = 抗终止进程.id();
    {
        let mut 服务记录表 = 服务表().lock().unwrap();
        let 条目 = 服务记录表.get_mut(&句柄).unwrap();
        条目.子进程.kill().unwrap();
        条目.子进程.wait().unwrap();
        条目.进程号 = 进程号;
        条目.子进程 = 抗终止进程;
    }
    let 释放线程组: Vec<_> = (0..4).map(|_| std::thread::spawn(move || 释放(句柄, true))).collect();
    for 释放线程 in 释放线程组 { assert_eq!(释放线程.join().unwrap(), Ok(true)); }
    assert!(!服务存在(句柄));
    assert!(!Command::new("/bin/ps").args(["-p", &进程号.to_string()]).stdout(Stdio::null()).status().unwrap().success());
}
