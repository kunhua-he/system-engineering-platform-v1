#!/bin/sh
# 命令行界面 —— shell 包装（胶水只做第一步：找到解释器，再把参数原样交出去）。
#
# 上级：系统工程平台 V1 ／ 落点：`前端呈现/命令行界面/`
# 形态依据：`项目文档/设计文档/代码形态分工.md` 第一节表 6 —— 本落点是「shell（胶水）+ 调接口面的 HTTP」。
#
# 标识符**一律 ASCII**（`sh` 不认非 ASCII 变量名与函数名）：
#   ① 函数名 `用法() {` ⇒ `not a valid identifier`
#   ② 变量赋值 `腿=x` ⇒ `command not found`
#   ③ **变量展开后紧跟中文字符** ⇒ `"${leg}（分支"` 必须写成 `${leg}`，否则中文被当成变量名的一部分
# 三条都按 `代码形态分工.md` 一之二的实测登记守着。
#
# 它不做任何判断：端口、命令、参数一律透传（端口交给 python 那一侧按
# 「--端口 > 环境变量 V1_GATEWAY_PORT > 默认 43110」三档取）。
# 统一端口环境变量名 = `V1_GATEWAY_PORT`（ASCII；唯一落点
# `命令行界面.py::端口环境变量`，见 `接口面形状.md` §六）。本脚本**不读也不设**它 ——
# 读它的就两处：python 那一侧与部署侧 `流量端口`（台账 #50 收口）；
# Rust 网关只认命令行 `--端口`，不读环境变量。

set -eu

SELF_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "${SELF_DIR}/../.." && pwd)

# 解释器：优先仓库内 venv（构建环境/python），退到 PATH 上的 python3。
# 本界面只用标准库，任何 python3 都能跑；找不到就如实报缺什么。
VENV_PY="${REPO_ROOT}/构建环境/python/bin/python3"
if [ -x "${VENV_PY}" ]; then
    PY="${VENV_PY}"
else
    PY=$(command -v python3 || command -v python || true)
fi
if [ -z "${PY}" ]; then
    echo "起不来：找不到 python3。本界面只用标准库，装任意 python3 即可（仓库内 venv 在 构建环境/python/）。" >&2
    exit 127
fi

exec "${PY}" "${SELF_DIR}/命令行界面.py" "$@"
