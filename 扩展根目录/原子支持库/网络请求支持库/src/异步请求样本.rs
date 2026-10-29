use v1_contract::{数据槽, 类型标签};
use v1_contract::复合值载荷::{复合元素, 复合值, 编码复合值载荷, 解码复合值载荷};
use std::io::{Read, Write};
use std::net::TcpListener;
use std::time::{Duration, Instant};

fn 按名调用(能力名称: &str, 参数槽表: &[数据槽]) -> 数据槽 {
    let 命令声明 = crate::命令声明面::造命令表();
    let 命令位置 = 命令声明.iter().position(|命令项| unsafe {
        std::ffi::CStr::from_ptr(命令项.名称.cast()).to_str().unwrap() == 能力名称
    }).unwrap_or_else(|| panic!("能力尚未实现：{能力名称}"));
    let mut 返回数据槽 = 数据槽::空槽();
    unsafe { crate::执行函数面::执行函数表[命令位置](&mut 返回数据槽, 参数槽表.len() as u32, 参数槽表.as_ptr()); }
    返回数据槽
}

fn 取结构并归还(返回数据槽: 数据槽) -> Vec<复合元素> {
    assert_eq!(返回数据槽.类型标签.取号值(), 103);
    let 返回长度 = 返回数据槽.槽字节长度 as usize;
    let 返回地址 = 返回数据槽.槽值 as *mut u8;
    let 返回字节 = unsafe { Box::from_raw(std::ptr::slice_from_raw_parts_mut(返回地址, 返回长度)) };
    解码复合值载荷(&返回字节, 103).unwrap()
}

#[test]
fn 测试慢请求提交立即返回且轮询取得真实正文() {
    let 样本监听 = TcpListener::bind("127.0.0.1:0").unwrap();
    let 请求地址 = format!("http://{}/slow", 样本监听.local_addr().unwrap());
    let 服务线程 = std::thread::spawn(move || {
        let (mut 连接样本, _) = 样本监听.accept().unwrap();
        let mut 请求缓冲 = [0; 4096];
        assert!(连接样本.read(&mut 请求缓冲).unwrap()>0);
        std::thread::sleep(Duration::from_millis(1300));
        连接样本.write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 4\r\nConnection: close\r\n\r\nreal").unwrap();
    });
    let 请求元素 = vec![
        复合元素{名称:"地址".into(),值:复合值::文本载荷(请求地址)},
        复合元素{名称:"允许回环".into(),值:复合值::逻辑型(true)},
        复合元素{名称:"超时秒".into(),值:复合值::双精度(3.0)},
    ];
    let 请求字节 = 编码复合值载荷(101, &请求元素).unwrap();
    let 请求槽 = 数据槽::指针(类型标签::构造(101), 请求字节.as_ptr() as u64, 请求字节.len() as u64, false);
    let 开始计时 = Instant::now();
    let 任务槽 = 按名调用("提交网络请求", &[请求槽]);
    assert_eq!(任务槽.类型标签.取号值(), 7);
    assert_ne!(任务槽.槽值, 0);
    assert!(开始计时.elapsed() < Duration::from_millis(900));
    loop {
        let 结果元素 = 取结构并归还(按名调用("读取网络任务", &[任务槽]));
        let 完成字段 = 结果元素.iter().find(|元素项| 元素项.名称=="已完成").unwrap();
        if 完成字段.值 == 复合值::逻辑型(true) {
            let 正文字段 = 结果元素.iter().find(|元素项| 元素项.名称=="响应文本").unwrap();
            assert_eq!(正文字段.值, 复合值::文本载荷("real".into()));
            break;
        }
        assert!(开始计时.elapsed() < Duration::from_secs(5));
        std::thread::sleep(Duration::from_millis(10));
    }
    assert_eq!(按名调用("释放网络任务", &[任务槽]).槽值, 1);
    assert_eq!(按名调用("读取网络任务", &[任务槽]).类型标签.取号值(), u32::MAX);
    服务线程.join().unwrap();
}
