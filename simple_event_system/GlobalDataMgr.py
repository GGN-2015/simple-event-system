from typing import Any
import functools

try:
    from .AbstractGlobalData import ConcreteGlobalData, AbstractGlobalData, AbstractGlobalDataHook
    from .GetAllConcreteSubclass import get_all_concrete_subclasses
except:
    from AbstractGlobalData import ConcreteGlobalData, AbstractGlobalData, AbstractGlobalDataHook
    from GetAllConcreteSubclass import get_all_concrete_subclasses


# 全局数据与钩子管理器
# 可以实时更新钩子序列
class GlobalDataMgr:
    def __init__(self) -> None:
        self._global_data = ConcreteGlobalData()
        self._data_hook_list:list[AbstractGlobalDataHook] = []


    # 如果用于使用变量时没有指明名字空间
    # 那么我们会默认它使用的是插件自己的名字空间
    @classmethod
    def wrap_key(cls, plugin_user:str, key:str, func_now:str) -> str:
        if key.find(".") == -1: # 如果用户不说明名字空间，默认用的是自己的
            key = plugin_user + "." + key
        if len(key.split(".")) < 2:
            raise ValueError(f"{cls.__name__}.{func_now}: key should has at least two parts.")
        return key

    def hook_deactivate(self, hook_name:str):
        if hook_name in self.get_hook_name_list():
            pos = -1
            for idx, hook_item in enumerate(self._data_hook_list):
                if hook_item.identifier() == hook_name:
                    pos = idx
                    break
            if pos != -1:
                self._data_hook_list.pop(pos) # 从队列中删除插件
                self.get_hook_list_for_plugin.cache_clear()

    def hook_activate(self, hook_name:str):

        # 截取类型名称和实例名称
        class_name = hook_name
        instance_name = ""
        if class_name.find("_") != -1:
            class_name, instance_name = hook_name.split("_", maxsplit=1)

        for hook_type in get_all_concrete_subclasses(AbstractGlobalDataHook):
            obj = hook_type()
            assert isinstance(obj, AbstractGlobalDataHook)

            # 设置实例名称
            obj.set_instance_name(instance_name)
            if type(obj).__name__ == class_name:
                self.add_hook_to_list(obj)
                return
        raise ValueError(f"GlobalDataMgr.plugin_activate: {hook_name} is not a hook identifier.")
    
    def add_hook_to_list(self, hook_obj:AbstractGlobalDataHook):
        if hook_obj.identifier() not in self.get_hook_name_list():
            self._data_hook_list.append(hook_obj)
            self._data_hook_list.sort(
                key=lambda hook:(hook.priority(), hook.identifier()))
            self.get_hook_list_for_plugin.cache_clear()

    # 设置全局事件系统
    def set_event_system(self, new_event_system:Any):
        self._global_data.set_event_system(new_event_system)


    # 设置一个值
    def put(self, plugin_name:str, key:str, val:Any):
        with self.rlock():
            key = GlobalDataMgr.wrap_key(plugin_name, key, "put")
            return self.get_global_data_object_for_plugin(plugin_name).put(plugin_name, key, val)


    # 读取一个值
    def get(self, plugin_name:str, key:str) -> Any:
        with self.rlock():
            key = GlobalDataMgr.wrap_key(plugin_name, key, "get")
            return self.get_global_data_object_for_plugin(plugin_name).get(plugin_name, key)


    # 返回当前锁对象
    def rlock(self):
        return self._global_data.thread_rlock


    # 获得当前正在工作的所有钩子序列
    def get_hook_name_list(self) -> list[str]:
        return [hook.identifier() for hook in self._data_hook_list]


    # 获取和某个插件类型
    # 相关的所有钩子列表
    @functools.cache
    def get_hook_list_for_plugin(self, plugin_type:str) -> list[AbstractGlobalDataHook]:
        hook_list:list[AbstractGlobalDataHook] = []
        for hook in self._data_hook_list:
            if hook.match_plugin(plugin_type): # 这个钩子对当前插件有影响
                hook_list.append(hook)
        return hook_list


    # 给定一个插件名
    # 找到这个插件对应的，钩子过后的 AbstractGlobalData
    # 特别的，EventSystem 也是 plugin_name
    def get_global_data_object_for_plugin(self, plugin_name:str) -> AbstractGlobalData:
        hook_list = self.get_hook_list_for_plugin(plugin_name) # 获得钩子列表
        
        # 如果没有任何合法的钩子
        if len(hook_list) == 0:
            return self._global_data
        
        # 如果有至少一个合法的钩子
        # 按照次序，将所有钩子穿起来（每个钩子都有上游）
        abs_data_now = self._global_data
        for hook in hook_list:
            hook.upstream(abs_data_now) # 串联上下游
            abs_data_now = hook
        return abs_data_now
