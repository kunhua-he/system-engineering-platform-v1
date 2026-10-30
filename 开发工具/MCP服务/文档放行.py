"""纯文档放行路由；非文档99交还原完整链，不静默绕过。"""
import sys
import time
from pathlib import Path
起始时刻 = time.monotonic()
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from 构建装配.门禁 import 自门禁
from 开发工具.MCP服务.验证管理.文档分流 import 执行文档放行

if __name__ == "__main__":
    sys.exit(自门禁(起始时刻, 执行文档放行(sys.argv[1:]), 尾巴余量毫秒=200, 修法="文档档只执行静态门禁；失败保留原码，源码转原完整链"))
