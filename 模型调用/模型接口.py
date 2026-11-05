"""模型 HTTP 门面 —— 让 HTML 一个请求就拿到答案。

起法：

    python3 /Users/hekunhua/Documents/Agent/PHP/系统工程平台V1/模型调用/模型接口.py

HTML 里的用法（就这一句）：

    const 回 = await fetch("http://127.0.0.1:43111/对话", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({消息: "你好"})
    }).then(r => r.json());
    console.log(回.内容);

为什么需要这一层：底座 43110 是「一次调用一个能力」，一次对话要打二十次请求
（拉起→轮询就绪→许可→连接→提交→轮询结果→归还→清理），而且它不发 CORS 头，
浏览器跨域会被直接拦下。这一层把整条链封进一次请求，并补上 CORS。
"""

import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 模型

端口 = 43111


class 处理(BaseHTTPRequestHandler):
    协议版本 = "HTTP/1.1"

    def _回(self, 码, 体):
        数据 = json.dumps(体, ensure_ascii=False).encode()
        self.send_response(码)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(数据)))
        # 允许任意本地页面调用：这一层只服务本机，不对外。
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()
        self.wfile.write(数据)

    def do_OPTIONS(self):
        self._回(204, {})

    def _路径(self):
        """浏览器会把中文路径自动 URL 编码，比对前先解开。"""
        return urllib.parse.unquote(self.path)

    def do_GET(self):
        if self._路径().startswith("/状态"):
            try:
                self._回(200, {"成功": True, "值": 模型.状态()})
            except 模型.模型错误 as 错:
                self._回(200, {"成功": False, "错误": str(错)})
        else:
            self._回(200, {"成功": True, "说明": "POST /对话 {消息} · POST /看图 {图片,问题} · GET /状态"})

    def do_POST(self):
        路径 = self._路径()
        长度 = int(self.headers.get("Content-Length") or 0)
        try:
            入参 = json.loads(self.rfile.read(长度) or b"{}")
        except ValueError:
            self._回(400, {"成功": False, "错误": "请求体不是合法 JSON"})
            return
        try:
            if 路径.startswith("/对话"):
                内容 = 模型.对话(
                    入参.get("消息", ""),
                    系统提示词=入参.get("系统提示词", ""),
                    温度=入参.get("温度", 0.7),
                    最大令牌数=入参.get("最大令牌数", 2048),
                    超时秒=入参.get("超时秒", 180),
                )
                self._回(200, {"成功": True, "内容": 内容})
            elif 路径.startswith("/看图"):
                内容 = 模型.看图(
                    入参.get("图片", ""),
                    问题=入参.get("问题", "描述这张图"),
                    超时秒=入参.get("超时秒", 180),
                )
                self._回(200, {"成功": True, "内容": 内容})
            else:
                self._回(404, {"成功": False, "错误": "没有这个路径：%s" % 路径})
        except 模型.模型错误 as 错:
            # 错误名原样透出（如「资源受限（码 2506）」），不要笼统的「调用失败」。
            self._回(200, {"成功": False, "错误": str(错)})
        except Exception as 错:
            self._回(500, {"成功": False, "错误": "%s: %s" % (type(错).__name__, 错)})

    def log_message(self, format, *args):
        sys.stderr.write("模型接口 %s\n" % (format % args))


if __name__ == "__main__":
    print("模型接口已起：http://127.0.0.1:%d" % 端口)
    print("  POST /对话 {\"消息\":\"你好\"}")
    print("  POST /看图 {\"图片\":\"/绝对路径.jpg\"}")
    print("  GET  /状态")
    ThreadingHTTPServer(("127.0.0.1", 端口), 处理).serve_forever()
