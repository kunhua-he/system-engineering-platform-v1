import Foundation
import PDFKit
import AppKit
import CoreGraphics

// PDF 处理原生执行体：页数/加密、整页渲染、内嵌图提取、结构校验。
// 子命令：页数 <路径> | 渲染 <路径> <页序号> <输出路径> <倍率> | 提取 <路径> <页序号> | 校验 <路径> | --预热
// 退出码：0 成功 2 参数不合法 3 文件不可读 4 资源超限 5 页序号越界 6 处理失败 7 平台不支持

func 输出(_ 输出字典: [String: Any]) -> Int32 {
    guard let 字节 = try? JSONSerialization.data(withJSONObject: 输出字典, options: [.sortedKeys]) else { return 6 }
    if 字节.count > 88_000_000 { return 4 }
    FileHandle.standardOutput.write(字节)
    return 0
}

func 打开文档(_ 路径: String) -> PDFDocument? {
    guard FileManager.default.fileExists(atPath: 路径) else { return nil }
    return PDFDocument(url: URL(fileURLWithPath: 路径))
}

func 页数_(_ 文档: PDFDocument) -> Int {
    var 页面计数 = 0
    while 文档.page(at: 页面计数) != nil { 页面计数 += 1 }
    return 页面计数
}

func 预热图() -> CGImage? {
    guard let 画布 = CGContext(data: nil, width: 64, height: 64, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceRGB(),
                              bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return nil }
    画布.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    画布.fill(CGRect(x: 0, y: 0, width: 64, height: 64))
    return 画布.makeImage()
}

func 执行预热() -> Int32 {
    guard let 首页页对象 = PDFDocument().page(at: 0) ?? nil else {
        // 空文档也可能没有页，直接产出一次位图渲染即可
        guard let 图像 = 预热图() else { return 6 }
        let 视图 = NSImageView(frame: NSRect(x: 0, y: 0, width: 64, height: 64))
        视图.image = NSImage(cgImage: 图像, size: NSSize(width: 64, height: 64))
        return 0
    }
    _ = 首页页对象
    return 0
}

let 参数 = CommandLine.arguments
if 参数.count >= 2 && 参数[1] == "--预热" { exit(autoreleasepool { 执行预热() }) }
guard 参数.count >= 3 else { exit(2) }
let 子命令 = 参数[1]
let 路径 = 参数[2]
guard 路径.hasPrefix("/") else { exit(2) }
// 先认文件头：非 PDF 属「格式不支持」（换格式），与「读不到文件」（查路径/权限）
// 是两种完全不同的处置 ⇒ 分成两个退出码，别让调用方按同一个码乱猜。
guard let 文件字节 = try? Data(contentsOf: URL(fileURLWithPath: 路径)),
      FileManager.default.fileExists(atPath: 路径) else { exit(3) }
guard 文件字节.prefix(5) == Data("%PDF-".utf8) else { exit(8) }
guard let 文档 = 打开文档(路径) else { exit(6) }
let 总页数 = 页数_(文档)

switch 子命令 {
case "页数":
    exit(autoreleasepool { 输出(["页数": 总页数, "加密": 文档.isEncrypted, "可打开": true]) })

// 文本：第三参 = 页序号（"all" 或 0 起的整数）⇒ 逐页取 PDFKit 的 string。
// 加密文档 PDFKit 取不到正文是正常的：如实报空串 + 加密标记，不猜不编。
case "文本":
    guard 参数.count >= 4 else { exit(2) }
    let 页参数 = 参数[3]
    var 页序表: [Int] = []
    if 页参数 == "all" {
        页序表 = Array(0..<总页数)
    } else {
        guard let 单页 = Int(页参数), 单页 >= 0 else { exit(2) }
        guard 单页 < 总页数 else { exit(5) }
        页序表 = [单页]
    }
    if 页序表.count > 2000 { exit(4) }
    var 页结果表: [[String: Any]] = []
    var 总字符数 = 0
    var 输出字节预算 = 0
    for 序 in 页序表 {
        let 正文 = 文档.page(at: 序)?.string ?? ""
        总字符数 += 正文.count
        输出字节预算 += 正文.utf8.count
        if 输出字节预算 > 80 * 1024 * 1024 { exit(4) }
        页结果表.append(["页序号": 序, "字符数": 正文.count, "文本": 正文])
    }
    exit(autoreleasepool {
        输出(["页数": 总页数, "加密": 文档.isEncrypted, "取页数": 页结果表.count,
              "总字符数": 总字符数, "页文本": 页结果表])
    })

case "校验":
    var 版本 = "未知"
    if let 首页 = 文档.page(at: 0)?.pageRef?.dictionary {
        let 值: CGPDFStringRef? = nil
        // PDF 头版本读文件前 8 字节更可靠，这里读不到就报未知，不猜
        if let 文件头 = try? String(contentsOfFile: 路径, encoding: .isoLatin1).prefix(9), 文件头.hasPrefix("%PDF-") {
            版本 = String(文件头.dropFirst(5)).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        _ = 值
        _ = 首页
    } else if let 文件头 = try? String(contentsOfFile: 路径, encoding: .isoLatin1).prefix(9), 文件头.hasPrefix("%PDF-") {
        版本 = String(文件头.dropFirst(5)).trimmingCharacters(in: .whitespacesAndNewlines)
    }
    exit(autoreleasepool { 输出(["合法": 总页数 > 0, "页数": 总页数, "加密": 文档.isEncrypted, "版本": 版本]) })

case "渲染":
    guard 参数.count >= 5 else { exit(2) }
    guard let 页序号 = Int(参数[3]), 页序号 >= 0 else { exit(2) }
    let 输出路径 = 参数[4]
    guard 输出路径.hasPrefix("/") else { exit(2) }
    let 倍率 = 参数.count >= 6 ? (Double(参数[5]) ?? 2.0) : 2.0
    guard 倍率 > 0.1 && 倍率 <= 8.0 else { exit(4) }
    guard let 页面对象 = 文档.page(at: 页序号) else { exit(5) }
    let 边界 = 页面对象.bounds(for: .mediaBox)
    let 图宽 = Int(边界.width * 倍率), 图高 = Int(边界.height * 倍率)
    guard 图宽 > 0 && 图高 > 0 && 图宽 <= 20000 && 图高 <= 20000 && 图宽 * 图高 <= 100_000_000 else { exit(4) }
    let 页面图 = NSImage(size: NSSize(width: 图宽, height: 图高))
    页面图.lockFocus()
    NSColor.white.setFill(); NSRect(x: 0, y: 0, width: 图宽, height: 图高).fill()
    if let 上下文 = NSGraphicsContext.current?.cgContext {
        上下文.scaleBy(x: 倍率, y: 倍率)
        页面对象.draw(with: .mediaBox, to: 上下文)
    }
    页面图.unlockFocus()
    guard let tiff = 页面图.tiffRepresentation, let 位图 = NSBitmapImageRep(data: tiff),
          let png = 位图.representation(using: .png, properties: [:]) else { exit(6) }
    do { try png.write(to: URL(fileURLWithPath: 输出路径)) } catch { exit(6) }
    exit(autoreleasepool { 输出(["输出路径": 输出路径, "宽": 图宽, "高": 图高, "字节数": png.count, "页序号": 页序号, "倍率": 倍率]) })

case "提取":
    guard 参数.count >= 4, let 页序号 = Int(参数[3]), 页序号 >= 0 else { exit(2) }
    guard let 页面对象 = 文档.page(at: 页序号), let 页引用 = 页面对象.pageRef, let 页字典 = 页引用.dictionary else { exit(5) }

    final class 收集器 {
        var 图像: [[String: Any]] = []
        var 跳过: [String] = []
        var 超限 = false
        var 已访问 = 0
    }

    // 回调上下文：当前要遍历的表 + 递归深度 + 收集器
    final class 遍历上下文 {
        let 收集: 收集器
        let 深度: Int
        init(_ 收集: 收集器, _ 深度: Int) { self.收集 = 收集; self.深度 = 深度 }
    }

    func 遍历图像表(_ 表: CGPDFDictionaryRef, _ 收集: 收集器, _ 深度: Int) {
        if 深度 > 4 || 收集.超限 { return }
        typealias 回调 = @convention(c) (UnsafePointer<Int8>, CGPDFObjectRef, UnsafeMutableRawPointer?) -> Void
        let 处理: 回调 = { 名称指针, 对象值, 上下文 in
            guard let 上下文 = 上下文 else { return }
            let 环境 = Unmanaged<遍历上下文>.fromOpaque(上下文).takeUnretainedValue()
            let 收集盒 = 环境.收集
            if 收集盒.已访问 >= 128 { 收集盒.超限 = true; return }
            收集盒.已访问 += 1
            let 名称 = String(cString: 名称指针)
            var 流引用: CGPDFStreamRef? = nil
            guard CGPDFObjectGetValue(对象值, .stream, &流引用), let 流 = 流引用,
                  let 流字典 = CGPDFStreamGetDictionary(流) else { return }
            // 先看 Subtype：Form 要递归进它的 Resources，Image 才取数据
            var 子类型指针: UnsafePointer<Int8>? = nil
            var 子类型 = ""
            if CGPDFDictionaryGetName(流字典, "Subtype", &子类型指针), let 子类型指针 = 子类型指针 {
                子类型 = String(cString: 子类型指针)
            }
            if 子类型 == "Form" {
                var 内部资源: CGPDFDictionaryRef? = nil
                if CGPDFDictionaryGetDictionary(流字典, "Resources", &内部资源), let 内部资源 = 内部资源 {
                    var 内部对象: CGPDFDictionaryRef? = nil
                    if CGPDFDictionaryGetDictionary(内部资源, "XObject", &内部对象), let 内部对象 = 内部对象 {
                        遍历图像表(内部对象, 收集盒, 环境.深度 + 1)
                    }
                }
                return
            }
            var 过滤器: CGPDFObjectRef? = nil
            var 编码 = "未知"
            if CGPDFDictionaryGetObject(流字典, "Filter", &过滤器), let 过滤器 = 过滤器 {
                var 编码名指针: UnsafePointer<Int8>? = nil
                if CGPDFObjectGetValue(过滤器, .name, &编码名指针), let 编码名指针 = 编码名指针 {
                    编码 = String(cString: 编码名指针)
                } else {
                    // Filter 常写成数组，如 ["DCTDecode"]；取首个编码名
                    var 编码数组: CGPDFArrayRef? = nil
                    if CGPDFObjectGetValue(过滤器, .array, &编码数组), let 编码数组 = 编码数组,
                       CGPDFArrayGetCount(编码数组) > 0 {
                        var 编码项: UnsafePointer<Int8>? = nil
                        if CGPDFArrayGetName(编码数组, 0, &编码项), let 编码项 = 编码项 { 编码 = String(cString: 编码项) }
                    }
                }
            }
            // CGPDFStreamCopyData 会自行应用解码器（ASCII85/Flate 都会展开），
            // 返回的格式才是真相：jpegEncoded 才能直接落地成图。
            var 格式 = CGPDFDataFormat.raw
            guard let 数据对象 = CGPDFStreamCopyData(流, &格式) else { return }
            let 数据体 = 数据对象 as Data
            guard 格式 != .raw else {
                收集盒.跳过.append("\(名称):\(编码):原始像素流未转图")
                return
            }
            if 数据体.count > 24 * 1024 * 1024 { 收集盒.超限 = true; return }
            收集盒.图像.append(["名称": 名称, "编码": "jpeg", "base64": 数据体.base64EncodedString(), "字节数": 数据体.count])
        }
        let 环境 = 遍历上下文(收集, 深度)
        withExtendedLifetime(环境) {
            CGPDFDictionaryApplyFunction(表, 处理, Unmanaged.passUnretained(环境).toOpaque())
        }
    }

    let 收集 = 收集器()
    var 资源引用: CGPDFDictionaryRef? = nil
    if CGPDFDictionaryGetDictionary(页字典, "Resources", &资源引用), let 资源 = 资源引用 {
        var 对象引用: CGPDFDictionaryRef? = nil
        if CGPDFDictionaryGetDictionary(资源, "XObject", &对象引用), let 对象表 = 对象引用 {
            if CGPDFDictionaryGetCount(对象表) > 64 { exit(4) }
            遍历图像表(对象表, 收集, 0)
        }
    }
    if 收集.超限 { exit(4) }
    let 总字节 = 收集.图像.reduce(0) { $0 + (($1["base64"] as? String)?.utf8.count ?? 0) }
    if 总字节 > 80 * 1024 * 1024 { exit(4) }
    // `未提取` 恒在（空表也返回）：契约字段不随数据有无而消失，调用方不必判键存在性。
    let 结果字典: [String: Any] = ["页序号": 页序号, "内嵌图数量": 收集.图像.count,
                                  "图像列表": 收集.图像, "未提取": 收集.跳过]
    exit(autoreleasepool { 输出(结果字典) })

default:
    exit(2)
}
