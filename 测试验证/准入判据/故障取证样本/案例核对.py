"""只读核对既有v1-case-runner回执；不扩展其案例或报告schema。"""

import json
import re
from pathlib import Path


def 核对案例读数(案例清单, 期望清单, 回执值, 提交哈希):
    失败明细 = []
    if not all(isinstance(成员值, dict) for 成员值 in (案例清单, 期望清单, 回执值)):
        return {"结果": "失败", "失败明细": ["案例、期望或回执不是对象"]}
    if (not isinstance(提交哈希, str) or not re.fullmatch("[0-9a-f]{40}", 提交哈希)
            or 回执值.get("提交哈希") != 提交哈希):
        失败明细.append("源码提交哈希不符")
    if 回执值.get("案例名") != 案例清单.get("案例名"):
        失败明细.append("案例名不符")
    if 回执值.get("结果") != "通过" or type(回执值.get("工作区是否干净")) is not bool:
        失败明细.append("不是既有runner的通过回执")
    for 字段名称 in ("死在哪一层", "死在哪一步", "错误码"):
        if 字段名称 not in 回执值 or 回执值[字段名称] is not None:
            失败明细.append("通过回执顶层应保留空失败字段:" + 字段名称)
    for 字段名称 in ("跑的时间", "说明"):
        if not isinstance(回执值.get(字段名称), str) or not 回执值[字段名称]:
            失败明细.append("缺少回执字段:" + 字段名称)
    if type(回执值.get("耗时微秒")) is not int or 回执值["耗时微秒"] < 0:
        失败明细.append("顶层耗时非法")
    步骤清单 = 案例清单.get("步骤")
    期望步骤 = 期望清单.get("步骤")
    实际步骤 = 回执值.get("步骤")
    if (not isinstance(步骤清单, list) or not 步骤清单
            or not isinstance(期望步骤, list) or not isinstance(实际步骤, list)
            or len(步骤清单) != len(期望步骤) or len(步骤清单) != len(实际步骤)):
        return {"结果": "失败", "失败明细": 失败明细 + ["步骤数量不符或空证据"]}
    for 序号, (定义值, 期望值, 实际值) in enumerate(zip(步骤清单, 期望步骤, 实际步骤)):
        位置名称 = "步骤[%d]" % 序号
        if not all(isinstance(成员值, dict) for 成员值 in (定义值, 期望值, 实际值)):
            失败明细.append(位置名称 + "不是对象")
            continue
        if 实际值.get("名") != 定义值.get("名") or 实际值.get("符合期望") is not True:
            失败明细.append(位置名称 + "名称错或没有真实判定")
        路由键表 = [字段名称 for 字段名称 in ("能力编号", "通知号", "读留痕") if 字段名称 in 定义值]
        if len(路由键表) != 1 or type(定义值.get(路由键表[0])) is not int:
            失败明细.append(位置名称 + "案例路由缺失或冲突")
        else:
            路由键名 = 路由键表[0]
            种类期望 = {"能力编号": "能力", "通知号": "通知", "读留痕": "读留痕"}[路由键名]
            编号期望 = 定义值[路由键名] if 路由键名 == "能力编号" else 0
            if (type(实际值.get("能力编号")) is not int or 实际值["能力编号"] != 编号期望
                    or 实际值.get("种类") != 种类期望):
                失败明细.append(位置名称 + "步骤路由不符")
        if 实际值.get("调用结果") != 期望值.get("结果"):
            失败明细.append(位置名称 + "调用结果不符，不能以案例通过冒充调用成功")
        if type(实际值.get("耗时微秒")) is not int or 实际值["耗时微秒"] < 0:
            失败明细.append(位置名称 + "耗时非法")
        if 期望值.get("结果") == "失败":
            错误期望 = 期望值.get("错误码")
            错误实际 = 实际值.get("错误码")
            if (not isinstance(错误期望, dict) or not isinstance(错误实际, dict)
                    or set(错误期望) != {"码", "名称", "可重试", "可自愈", "需人工"}
                    or any(type(错误实际.get(字段名称)) is not type(字段值)
                           or 错误实际.get(字段名称) != 字段值 for 字段名称, 字段值 in 错误期望.items())
                    or 实际值.get("死在哪一层") != 期望值.get("死在哪一层")
                    or not isinstance(实际值.get("死在哪一步"), str) or not 实际值["死在哪一步"]):
                失败明细.append(位置名称 + "失败层/错误码未独立吻合期望")
        elif 期望值.get("结果") == "成功":
            if any(字段名称 not in 实际值 or 实际值[字段名称] is not None
                   for 字段名称 in ("死在哪一层", "死在哪一步", "错误码")):
                失败明细.append(位置名称 + "成功调用带失败字段")
        else:
            失败明细.append(位置名称 + "期望不是成功/失败")
    return {"结果": "通过" if not 失败明细 else "失败", "失败明细": 失败明细,
            "证据范围": "既有案例回执一致性，产物仍由原runner判定",
            "制品与配置预算": "原回执不含，缺材料，不由本检查器补造"}


def 核对案例回执(回执路径, 案例目录, 提交哈希):
    案例目录 = Path(案例目录)
    案例清单 = json.loads((案例目录 / "案例.json").read_text(encoding="utf-8"))
    期望清单 = json.loads((案例目录 / "期望.json").read_text(encoding="utf-8"))
    候选回执 = None
    with Path(回执路径).open("rb") as 回执句柄:
        while 回执行 := 回执句柄.readline(1048577):
            if len(回执行) > 1048576:
                raise ValueError("既有回执行超过1MiB，拒绝无界读")
            回执值 = json.loads(回执行)
            if not isinstance(回执值, dict):
                raise ValueError("既有回执不是对象")
            if 回执值.get("案例名") == 案例清单.get("案例名"):
                候选回执 = 回执值
    if 候选回执 is None:
        return {"结果": "未判", "原因": "缺本案例运行回执"}
    return 核对案例读数(案例清单, 期望清单, 候选回执, 提交哈希)
