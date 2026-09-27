# -*- coding: utf-8 -*-
"""时间 —— 取当前时刻 · 格式化/解析账本时间戳（同一套格式）。"""

import datetime
import time

from .常量 import TIME_FMT


def now_ts():
    return time.time()


def fmt_ts(ts):
    return datetime.datetime.fromtimestamp(ts).astimezone().strftime(TIME_FMT)


def parse_ts(s):
    return datetime.datetime.strptime(s, TIME_FMT).timestamp()
