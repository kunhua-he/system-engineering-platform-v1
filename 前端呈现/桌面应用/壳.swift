// 桌面应用 —— 薄壳：把 `前端呈现/网页应用/` 装进系统 WebView（macOS 的 WKWebView）。
//
// 判据（`项目文档/设计文档/代码形态分工.md` 第 7 节）：**同一个网页应用 + 一个壳，不重写 UI**。
// 重写一套 UI 就是两条腿；这里一行 UI 都没有，只有「开个窗口、把同一个网址装进去」。
//
// 用 `swift 壳.swift <URL>` 直接跑（解释执行，**没有构建产物**、没有包管理、没有第三方依赖）。
// URL 由 `启动.sh` 从契约端口拼好传进来 —— 本文件**不写端口**（端口只有一个来源）。
//
// 非主线：README 明说 `前端呈现/` 是人类界面、非主线，所以这里只落形状 + 一个能跑的最小壳。

import AppKit
import WebKit

/// 最小壳：一个窗口 + 一个 WKWebView，窗口一关就退出。
final class 桌面壳: NSObject, NSApplicationDelegate {
    var 窗口: NSWindow!
    var 视图: WKWebView!
    let 地址: String

    init(地址: String) {
        self.地址 = 地址
        super.init()
    }

    func applicationDidFinishLaunching(_ 通知: Notification) {
        let 窗口框 = NSRect(x: 0, y: 0, width: 1180, height: 840)
        视图 = WKWebView(frame: 窗口框)
        窗口 = NSWindow(
            contentRect: 窗口框,
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        窗口.title = "系统工程平台 · 对外接口面"
        窗口.contentView = 视图
        窗口.center()
        窗口.makeKeyAndOrderFront(nil)

        guard let 网址 = URL(string: 地址) else {
            FileHandle.standardError.write(Data("壳：URL 拼不出来：\(地址)\n".utf8))
            NSApp.terminate(nil)
            return
        }
        视图.load(URLRequest(url: 网址))
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ 应用实例: NSApplication) -> Bool {
        true
    }
}

let 参数 = Array(CommandLine.arguments.dropFirst())
guard let 地址 = 参数.first else {
    FileHandle.standardError.write(Data(
        "壳：要一个 URL。请用 启动.sh 起（它从 契约声明/常量表.json 现读接口端口）。\n".utf8
    ))
    exit(2)
}

let 应用实例 = NSApplication.shared
let 应用代理 = 桌面壳(地址: 地址)
应用实例.delegate = 应用代理
应用实例.setActivationPolicy(.regular)
应用实例.run()
