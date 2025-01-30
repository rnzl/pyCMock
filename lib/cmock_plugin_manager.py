import importlib
import threading
from pathlib import Path


class CMockPluginManager:
    def __init__(self, config, utils):
        """
        Initialize the plugin manager with configuration and utility instances.
        """
        self.plugins = []
        plugins_to_load = ["expect"] + (config.plugins or [])
        plugins_to_load = list(dict.fromkeys(plugins_to_load))  # Remove duplicates while maintaining order
        for plugin in plugins_to_load:
            plugin_name = str(plugin)
            object_name = f"CMockGeneratorPlugin{self.camelize(plugin_name)}"
            with self._mutex:
                self._load_plugin(plugin_name, object_name, config, utils)
        self.plugins.sort(key=lambda plugin: plugin.priority)

    def run(self, method, args=None):
        """
        Execute the specified method on all loaded plugins.
        """
        if args is None:
            return "".join(
                plugin.run_method(method) for plugin in self.plugins if hasattr(plugin, method)
            )
        return "".join(
            plugin.run_method(method, args) for plugin in self.plugins if hasattr(plugin, method)
        )

    @staticmethod
    def camelize(lower_case_and_underscored_word):
        """
        Convert snake_case to CamelCase.
        """
        return "".join(
            word.capitalize() for word in lower_case_and_underscored_word.split("_")
        )

    @staticmethod
    @property
    def _mutex():
        """
        Provide a thread-safe mutex for plugin loading.
        """
        if not hasattr(CMockPluginManager, "_mutex_instance"):
            CMockPluginManager._mutex_instance = threading.Lock()
        return CMockPluginManager._mutex_instance

    def _load_plugin(self, plugin_name, object_name, config, utils):
        """
        Dynamically load a plugin.
        """
        try:
            # Construct file path for plugin
            file_name = Path(__file__).parent / f"cmock_generator_plugin_{plugin_name.lower()}.py"
            module_name = file_name.stem

            # Dynamically import module
            plugin_module = importlib.import_module(module_name)

            # Dynamically get the class from the module
            plugin_class = getattr(plugin_module, object_name)

            # Create an instance of the plugin and add it to the plugins list
            self.plugins.append(plugin_class(config, utils))

        except Exception as e:
            raise RuntimeError(
                f"ERROR: CMock unable to load plugin '{plugin_name}' '{object_name}' {file_name}"
            ) from e
