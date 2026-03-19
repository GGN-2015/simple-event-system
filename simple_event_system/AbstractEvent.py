from abc import ABC, abstractmethod
from typing import Any

# 所有抽象的事件对象
# 事件会在事件队列里传递
class AbstractEvent(ABC):

    # 所有抽象事件初始化时
    # 会把自己注册到一个指定的队列中
    def __init__(self) -> None:
        super().__init__()
    
    # 描述事件的名字
    # 一般建议同类事件名字相同，含义靠 message 区分
    @abstractmethod
    def identifier(self) -> str:
        return "AbstractEvent"

    # 所有的事件，必须可以携带一定的信息
    # 而这些信息以 dict 形式记录
    @abstractmethod
    def message(self) -> dict[str, Any]:
        return dict()


# 系统退出事件
# 系统退出事件表明系统正在退出（而不是命令插件退出的意思）
# 插件在接收到退出信号后，应该清理上下文，准备结束
class ExitEvent(AbstractEvent):
    def identifier(self) -> str:
        return "ExitEvent"
    def message(self) -> dict[str, Any]:
        return super().message()


# 系统进入事件
# 插件接收到进入事件后，应该准备初始化
class StartupEvent(AbstractEvent):
    def identifier(self) -> str:
        return "StartupEvent"
    def message(self) -> dict[str, Any]:
        return super().message()


# 定时器事件
class TimerEvent(AbstractEvent):
    def __init__(self, time_now:float) -> None:
        super().__init__()
        self._time_now = time_now

    def identifier(self) -> str:
        return "TimerEvent"
    
    # 返回闹钟响起的时刻
    def message(self) -> dict[str, Any]:
        return {"TimeNow": self._time_now}


# 键盘中断事件
class KeyboardInterruptEvent(AbstractEvent):
    def identifier(self) -> str:
        return "KeyboardInterruptEvent"
    def message(self) -> dict[str, Any]:
        return super().message()
