"""自有本地HTTP靶场，无凭据、无公网依赖，不替代V1能力返回。"""
from http.server import BaseHTTPRequestHandler as 请求处理器, ThreadingHTTPServer as 线程服务
from contextlib import contextmanager
import json
import threading
import time

网页原文='<html><head><title>门店123 &amp; 服务</title></head><body><h1>中文🙂</h1><p>订单123</p><a href="/shop">店铺</a><script>不应出现</script><style>也不出现</style></body></html>'


class 本地响应处理(请求处理器):
    def log_message(self,*日志参数):
        pass

    def do_GET(self):
        路径=self.path.split('?',1)[0]
        状态=200
        if 路径=='/html':字节=网页原文.encode()
        elif 路径=='/json':字节='{"标题":"中文🙂","订单":123}'.encode()
        elif 路径=='/bytes':字节=bytes([0,1,127,255])
        elif 路径=='/large':字节=b'x'*65537
        elif 路径=='/redirect':状态=302;字节=b''
        elif 路径=='/slow':time.sleep(3.3);字节=b'delayed'
        else:状态=404;字节=b'not-found'
        try:
            self.send_response(状态)
            self.send_header('Content-Type','application/octet-stream')
            self.send_header('Content-Length',str(len(字节)))
            if 状态==302:self.send_header('Location','/html')
            self.end_headers();self.wfile.write(字节)
        except (BrokenPipeError,ConnectionResetError):pass

    def do_POST(self):
        字节=self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200);self.send_header('Content-Length',str(len(字节)))
        self.end_headers();self.wfile.write(字节)


@contextmanager
def 本地靶场():
    服务=线程服务(('127.0.0.1',0),本地响应处理)
    服务.daemon_threads=True
    服务线程=threading.Thread(target=服务.serve_forever,daemon=True)
    服务线程.start()
    try:yield 'http://127.0.0.1:%s'%服务.server_port
    finally:
        服务.shutdown();服务.server_close();服务线程.join(timeout=2)
