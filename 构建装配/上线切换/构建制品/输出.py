"""输出 —— 装配器的唯一打印口（flush 掉，读日志时才不会滞后）。"""


def 打印文本(源文本: str) -> None:
    print(源文本, flush=True)
