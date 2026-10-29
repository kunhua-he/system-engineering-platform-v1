import Vision
import AppKit
import CoreGraphics
import Foundation
func 造预热图像() -> CGImage? {
    let 画布宽 = 128, 画布高 = 64
    guard let 画布 = CGContext(data: nil, width: 画布宽, height: 画布高, bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return nil }
    画布.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    画布.fill(CGRect(x: 0, y: 0, width: 画布宽, height: 画布高))
    return 画布.makeImage()
}
func 造识别请求() -> VNRecognizeTextRequest {
    let 识别请求 = VNRecognizeTextRequest()
    识别请求.recognitionLevel = .accurate
    // 当前系统默认设备报e5rt执行错误；固定CPU路径，不在失败后偷偷切换。
    识别请求.usesCPUOnly = true
    识别请求.recognitionLanguages = ["zh-Hans", "en-US"]
    识别请求.usesLanguageCorrection = true
    return 识别请求
}
func 执行预热() -> Int32 {
    guard let 图像对象 = 造预热图像() else { return 7 }
    let 识别请求 = 造识别请求()
    do { try VNImageRequestHandler(cgImage: 图像对象, options: [:]).perform([识别请求]) } catch { return 6 }
    return 0
}
if CommandLine.arguments.count != 2 { exit(2) }
if CommandLine.arguments[1] == "--预热" { exit(autoreleasepool { 执行预热() }) }
let 图片路径 = CommandLine.arguments[1]
func 执行识别() -> Int32 {
    guard let 图片对象 = NSImage(contentsOfFile: 图片路径), let 图像对象 = 图片对象.cgImage(forProposedRect: nil, context: nil, hints: nil) else { return 3 }
    if 图像对象.width > 4096 || 图像对象.height > 4096 { return 4 }
    let 识别请求 = 造识别请求()
    do { try VNImageRequestHandler(cgImage: 图像对象, options: [:]).perform([识别请求]) } catch { return 6 }
    let 观察列表 = (识别请求.results ?? []).sorted { 记录左, 记录右 in
        if abs(记录左.boundingBox.midY - 记录右.boundingBox.midY) < 0.000001 { return 记录左.boundingBox.minX < 记录右.boundingBox.minX }
        return 记录左.boundingBox.midY > 记录右.boundingBox.midY
    }
    if 观察列表.count > 2000 { return 4 }
    var 文字块: [[String: Any]] = []
    var 全部文字: [String] = []
    for 观察对象 in 观察列表 {
        guard let 候选对象 = 观察对象.topCandidates(1).first else { continue }
        let 当前矩形 = 观察对象.boundingBox
        全部文字.append(候选对象.string)
        文字块.append(["文字": 候选对象.string, "置信度": Double(候选对象.confidence), "左": Double(当前矩形.minX), "下": Double(当前矩形.minY), "宽": Double(当前矩形.width), "高": Double(当前矩形.height)])
    }
    guard let 输出字节 = try? JSONSerialization.data(withJSONObject: ["文字": 全部文字.joined(separator: "\n"), "文字块": 文字块], options: [.sortedKeys]) else { return 6 }
    if 输出字节.count > 65536 { return 4 }
    FileHandle.standardOutput.write(输出字节)
    return 0
}
exit(autoreleasepool { 执行识别() })
