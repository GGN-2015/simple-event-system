import threading
from abc import ABC, abstractmethod


try:
    from .AbstractEvent import AbstractEvent # 抽象事件
    from .GlobalDataMgr import GlobalDataMgr
except:
    from AbstractEvent import AbstractEvent # 抽象事件
    from GlobalDataMgr import GlobalDataMgr


# 描述一个抽象的插件
# 所有插件都应该以这个插件为基类
class AbstractPlugin(ABC):

    def __init__(self) -> None:
        super().__init__()

        # 对象实例名称：默认为空
        self.__instance_name = ""

        # 对象类型名称，其中不可以包含下划线
        self.__class_name = type(self).__name__
        if self.__class_name.find("_") != -1:
            raise ValueError("AbstractPlugin.__init__: type name include \'_\'.")


    # 设置实例名称
    # 可以用这种方式设置实例名称
    def set_instance_name(self, new_val:str):
        self.__instance_name = new_val
        if new_val.find("_") != -1:
            raise ValueError("AbstractPlugin.set_instance_name: instance name include \'_\'.")


    # 把当前插件对象加入插件队列
    def activate(self, event_system):

        # 插件名不能与系统基础冲突
        # EventSystem_ 开头的对象是 EventSystem 的非匿名实例
        # 也不可以用于系统命名
        if (self.identifier() == "EventSystem" 
                or self.identifier().startswith("EventSystem_")):
            raise ValueError("AbstractPlugin.activate: you can not activate a plugin called EventSystem.")
        event_system.plugin_activate(self.identifier())


    # 关闭当前插件
    # 从已经注册的插件列表中删除他
    def deactivate(self, event_system):
        event_system.plugin_deactivate(self.identifier())


    # 对象的名称，由类型名 + 对象实例 id 构成
    # 对象实例 id 为空的，则直接使用类型名称
    def identifier(self) -> str:
        return self.__class_name + (
            ("_" + self.__instance_name) if self.__instance_name else "")


    # 在插件系统中的优先级
    # priority 越小，优先级越高
    @abstractmethod
    def priority(self) -> float:
        return 0


    # 处理事件，并执行相关操作
    # 返回值为 True 表示不对事件进行拦截
    # 返回值为 False 表示对事件进行拦截，以后的插件不能获得其相关信息
    # 插件可以修改全局数据信息
    # 返回值中 list[AbstractEvent] 是当前插件释放到事件序列中的新事件
    @abstractmethod
    def process_event(self, global_data_mgr:GlobalDataMgr, event:AbstractEvent) -> tuple[bool, list[AbstractEvent]]:
        return True, []


# 事件调试器插件
# 会把所有经过这个插件的事件输出出来
class EventDebuggerPlugin(AbstractPlugin):
    def set_instance_name(self, new_val: str):
        if new_val != "":
            raise ValueError("EventDebuggerPlugin.set_instance_name: instance name is not empty.")
    def priority(self) -> float:
        return 0
    def process_event(self, global_data_mgr:GlobalDataMgr, event:AbstractEvent) -> tuple[bool, list[AbstractEvent]]:
        print("EventDebuggerPlugin:")
        print(f"    Event Now: {event.identifier()}: {event.message()}")
        if global_data_mgr.get(self.identifier(), "SystemStatusHook.SystemStatusHook.HookActive") is True:
            plugin_list = global_data_mgr.get(self.identifier(), "SystemStatusHook.ActivePluginList")
            print("    Plugin List:", plugin_list)
            hook_list = global_data_mgr.get(self.identifier(), "SystemStatusHook.ActiveHookList")
            print("    Hook List:", hook_list)
        print()
        return True, []


# 在遇到键盘中断时退出系统
# 将 EventSystem.Running 设置为 False 可以停止系统
class KeyboardInterruptExitPlugin(AbstractPlugin):
    def priority(self) -> float:
        return 10000
    def process_event(self, global_data_mgr:GlobalDataMgr, event:AbstractEvent) -> tuple[bool, list[AbstractEvent]]:
        if event.identifier() == "KeyboardInterruptEvent":
            
            # 去和调试器程序打配合
            # 如果调试器程序在工作，那么输出一个退出信息
            if global_data_mgr.get(
                    self.identifier(), 
                    "SystemStatusHook.EventDebuggerPlugin.PluginActive") is True:
                print(f"{self.identifier()}.process_event: Program Quit.")

            global_data_mgr.put(self.identifier(), "EventSystem.Running", False)
        return True, []
