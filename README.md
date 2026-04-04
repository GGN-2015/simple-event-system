# simple-event-system
A simple plugin, hook, and event-driven system framework.

## Install
```bash
pip install simple-event-system
```

## Introduction

In the current system, there are four main types of objects:

1. **Event**: When the system receives external input, events are sent to the event queue.
2. **Plugin**: Plugins act as event handlers. When a plugin is activated, it is added to the plugin queue.
3. **Global Data Area**: A shared storage space accessible to all plugins. Plugins can read from and write to this area, allowing them to influence the behavior of other plugins.
4. **Hook**: Hooks serve as middleware for the global data area. When plugins read from or write to the global data area, if hooks are configured, all operations will be routed through the hook methods to indirectly manipulate the global data.

### Plugins

Whenever an event occurs, it is dispatched to all activated plugins. These plugins are invoked in the order of their priority levels. After processing an event, a plugin has the following options:

1. Pass the event to the next plugin in the chain.
2. Stop propagating the event further.
3. Inject new events into the event queue (with the option to continue or stop propagating the current event; new events will trigger all plugins from the start when processed).

```python
# Derive new plugins from the AbstractPlugin class
from simple_event_system import AbstractPlugin, AbstractEvent, EventSystem

# Custom plugins must override the following methods
class MyPlugin(AbstractPlugin):

    # Plugin priority
    # Plugins with smaller priority values are executed first
    def priority(self) -> float:
        return 5000

    # Event processing method
    #   Returns two values:
    #   1. Boolean indicating whether to pass the event to downstream plugins (typically True)
    #   2. List of new events to append to the end of the event queue (typically empty list [])
    # Input parameters:
    #   event: has identifier() and message() methods to get event type and data
    #   global_data_mgr: has get() and put() methods for direct/indirect access to global data
    #   Note: global_data_mgr is hook-wrapped, so using it automatically triggers the hook chain
    def process_event(
        self, 
        global_data_mgr: GlobalDataMgr, 
        event: AbstractEvent) -> tuple[bool, list[AbstractEvent]]:

        # Do what you want before return
        return True, []

# Create event system instance
es = EventSystem(logfile_path)

# Start the event system (runs in a new thread, non-blocking)
es.run()

# Use this command after es.run() to start MyPlugin
es.put("SystemStatusHook.MyPlugin.PluginActive", True)

# Use this command after es.run() to stop MyPlugin
es.put("SystemStatusHook.MyPlugin.PluginActive", False)
```

Specifically, if you wish to start multiple instances of the same plugin, you may consider using the command:

```python
es.put("SystemStatusHook.MyPlugin_x.PluginActive", True)
```

where `x` is a number or a specified string without underscores. Except for some system-defined plugins, most plugins allow multiple instances of the same type to run in the system.

### Hooks

Without any hooks, all plugins access the global data area directly. With hooks configured, specific plugins can be forced to access the global data indirectly, enabling modification of plugin behavior.

When multiple hooks are attached to a plugin, they are chained in priority order: the hook with the smallest priority value operates on the actual data directly, the second smallest operates on the first hook, and so on. Plugins interact with the abstracted global data area provided by the highest-priority hook associated with them. Users don't need to manually add plugins to the plugin queue—EventSystem automatically discovers all existing plugins.

```python
# Derive new hooks from the AbstractGlobalDataHook class
from simple_event_system import AbstractGlobalDataHook, EventSystem

# Custom hooks must override the following methods
class MyHook(AbstractGlobalDataHook):

    # Priority value
    # Smaller values mean closer proximity to the actual global data
    def priority(self) -> int:
        return 5000

    # Determine if this hook applies to a specific plugin
    # Return True to apply to all plugins
    def match_plugin(self, plugin_name: str) -> bool: 
        return True

    # Exposed get interface for reading global data
    # Returning self.upstream_item.get(plugin_user, key) means no modification to the original functionality
    def get(self, plugin_user: str, key: str) -> Any:
        if self.upstream_item is None:
            raise ValueError()
        return self.upstream_item.get(plugin_user, key)

    # Exposed put interface for writing to global data
    # Returning self.upstream_item.put(plugin_user, key, val) means no modification to the original functionality
    def put(self, plugin_user: str, key: str, val: Any):
        if self.upstream_item is None:
            raise ValueError()
        return self.upstream_item.put(plugin_user, key, val)

# Create event system instance
es = EventSystem(logfile_path)

# Start the event system (runs in a new thread)
es.run()

# Use this command after es.run() to start MyHook
es.put("SystemStatusHook.MyHook.HookActive", True)

# Use this command after es.run() to stop MyHook
es.put("SystemStatusHook.MyHook.HookActive", True)
```

Specifically, if you wish to start multiple instances of the same hook, you may consider using the command:

```python
es.put("SystemStatusHook.MyHook_x.HookActive", True)
```

where `x` is a number or a specified string without underscores. Except for some system-defined hooks, most hooks allow multiple instances of the same type to run in the system.

### Events

Events are the primary driving force of the system. Users can customize events according to their needs. Each event contains a `message` (dictionary mapping strings to arbitrary types).

```python
# Derive new events from the AbstractEvent class
from simple_event_system import AbstractEvent

# Users can implement custom initialization methods for events
# To introduce events into the system:
# Recommended to use the second return value of a custom plugin's process_event method
class MyEvent(AbstractEvent):

    # Return event data (dictionary)
    def message(self) -> dict[str, Any]:
        return dict()
```

To add events to the event queue, use the second return value of the `process_event` method in custom plugins.

## Official Interfaces, Plugins and Hooks

### EventSystem

EventSystem is the manager for all plugins, but it also behaves like a plugin itself—its operation is controlled through global data. EventSystem primarily uses the following global variables:

1. `EventSystem.Running`: Boolean indicating whether the event system should continue running (default: `True`). Setting to `False` terminates the system.
2. `EventSystem.Timer`: Float value (default: `3.0`) specifying the interval (in seconds) at which EventSystem inserts a `TimerEvent` into the event queue. This `TimerEvent` includes a float `TimeNow` field representing the number of seconds the system has been running.
3. `EventSystem.Sleep`: Float value (default: `0.5`) specifying the maximum time (in seconds) EventSystem sleeps when the event queue is empty.

### EventDebuggerPlugin

EventDebuggerPlugin is a debugging plugin that prints full event information to the command line whenever an event occurs. This plugin is not enabled by default but can be activated as needed.

```python
from simple_event_system import EventSystem

# Create EventSystem Object
es = EventSystem(os.path.join(DIRNOW, "log.txt"))

# Start EventSystem thread
# Event is processed in another thread
es.run()

# Use SystemStatusHook to activate EventDebuggerPlugin
# es.put can only be used after es.run()
es.put("SystemStatusHook.EventDebuggerPlugin.PluginActive", True)

```

### KeyboardInterruptExitPlugin

KeyboardInterruptExitPlugin facilitates command-line program exit. When enabled, pressing `Ctrl+C` terminates EventSystem execution by setting `EventSystem.Running` to `False`. This plugin is enabled by default—without it, stopping EventSystem would be difficult.

```python
from simple_event_system import KeyboardInterruptExitPlugin, EventSystem

# Create EventSystem
es = EventSystem(os.path.join(DIRNOW, "log.txt"))

# Start EventSystem
es.run()

# If you do not want KeyboardInterruptExitPlugin, use this command
es.put("SystemStatusHook.KeyboardInterruptExitPlugin.PluginActive", False)

```

### SystemStatusHook

SystemStatusHook is a hook for easily viewing and managing system status. When enabled, the following global variables become available for querying system state (enabled by default—without it, managing other plugins/hooks would be inconvenient):

1. `SystemStatusHook.<PluginName>.PluginActive`: Check if a specific plugin is currently running.
2. `SystemStatusHook.<HookName>.HookActive`: Check if a specific hook is currently active.
3. `SystemStatusHook.ActivePluginList`: Read-only list of strings containing names of all running plugins.
4. `SystemStatusHook.ActiveHookList`: Read-only list of strings containing names of all active hooks.

Setting `SystemStatusHook.<PluginName>.PluginActive` or `SystemStatusHook.<HookName>.HookActive` to `True`/`False` enables/disables the specified plugins/hooks, providing a convenient control interface:
- Setting to `True` activates a plugin/hook (throws an exception if the target is undefined)
- Setting to `False` deactivates a plugin/hook (no error if the target is not running or doesn't exist)

This mechanism allows plugins/hooks to conveniently control the activation state of other components. Additionally, since EventSystem is treated as a special plugin, setting `SystemStatusHook.EventSystem.PluginActive` to `False` shuts down the entire system. Setting `SystemStatusHook.EventDebuggerPlugin.PluginActive` to `True` enables the debugging plugin.
