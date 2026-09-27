"""常量 —— 落点与环境变量（都在这一处，别处只引不抄）。"""

import os
import tempfile
from pathlib import Path

仓根 = Path(__file__).resolve().parents[3]
制品落点 = 仓根 / "构建装配" / "制品产物"
运行根 = Path(os.environ.get("ZCODE_SWITCH_RUN_ROOT") or Path(tempfile.gettempdir()) / "系统工程平台V1-上线切换")
健康超时秒 = 15.0
停等秒 = 5.0
