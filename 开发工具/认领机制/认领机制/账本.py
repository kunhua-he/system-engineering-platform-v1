# -*- coding: utf-8 -*-
"""账本 —— flock 互斥 + 原子替换（写账走「临时文件 + os.replace」）。"""

import fcntl
import hashlib
import json
import os
import tempfile

from .常量 import FORMAT_VERSION


class Ledger:
    """with Ledger(path) as led: 读改写全在锁内。锁文件落 /tmp（不进仓、不进版本库）。"""

    def __init__(self, path):
        self.path = path
        self.fd = None
        self.data = None

    def _lockpath(self):
        h = hashlib.sha1(os.path.abspath(self.path).encode("utf-8")).hexdigest()[:16]
        return os.path.join(tempfile.gettempdir(), "claim-ledger-%s.lock" % h)

    def _load(self):
        if not os.path.exists(self.path):
            return {"格式版本": FORMAT_VERSION, "租约": []}
        with open(self.path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return {"格式版本": FORMAT_VERSION, "租约": []}
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("租约"), list):
            raise ValueError("账本形状不对（缺「租约」数组）：%s" % self.path)
        return data

    def __enter__(self):
        d = os.path.dirname(self.path) or "."
        os.makedirs(d, exist_ok=True)
        self.fd = os.open(self._lockpath(), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)          # 认领/释放/回收的原子性靠它
        try:
            self.data = self._load()
        except BaseException:                        # 账本坏 ⇒ 关 fd 放锁再抛，
            self.__exit__(None, None, None)          # 否则锁被本进程的另一处 flock 永久挡住
            raise
        return self

    def __exit__(self, *exc):
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
        return False

    def save(self):
        self.data["租约"].sort(key=lambda l: l["腿标识"])   # 稳定序 ⇒ diff 只显示真变化
        d = os.path.dirname(self.path) or "."
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".账本-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, self.path)
