"""输出 —— 唯一打印口（flush 掉，读日志时才不会滞后）。"""


def 打印(文: str) -> None:
    print(文, flush=True)
