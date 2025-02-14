import importlib
import threading
from pathlib import Path


class CMockPluginManager:
    def __init__(self, config, utils):
        """
        Initialize the plugin manager with configuration and utility instances.
        """
        self.plugins = []
        plugins_to_load = [':expect'] + (config.options[':plugins'] or [])
        plugins_to_load = list(dict.fromkeys(plugins_to_load))  # Remove duplicates while maintaining order
        for plugin in plugins_to_load:
            plugin_name = str(plugin[1:])   # Remove leading colon
            object_name = f"CMockGeneratorPlugin{self.camelize(plugin_name)}"
            self._mutex.acquire()
            try:
                self._load_plugin(plugin_name, object_name, config, utils)
            finally:
                self._mutex.release()
        self.plugins.sort(key=lambda plugin: plugin.priority)

    def run(self, method, *args, **kwargs):
        """
        Execute the specified method on all loaded plugins.
        """
        data = ""
        for plugin in self.plugins:
            if hasattr(plugin, method):
                data += getattr(plugin, method)(*args, **kwargs)

        return data


    @staticmethod
    def camelize(lower_case_and_underscored_word):
        """
        Convert snake_case to CamelCase.
        """
        return "".join(
            word.capitalize() for word in lower_case_and_underscored_word.split("_")
        )

    @property
    def _mutex(self):
        """
        Provide a thread-safe mutex for plugin loading.
        """
        if not hasattr(self, "_mutex_instance"):
            self._mutex_instance = threading.Lock()
        return self._mutex_instance

    def _load_plugin(self, plugin_name, object_name, config, utils):
        """
        Dynamically load a plugin.
        """
        try:
            # Construct file path for plugin
            file_name = Path(__file__).parent / f"cmock_generator_plugin_{plugin_name.lower()}.py"
            module_name = file_name.stem

            # Debug print to check file path and module name
            # print(f"Loading plugin: {plugin_name}, file: {file_name}, module: {module_name}")

            # Dynamically import module
            plugin_module = importlib.import_module(module_name)

            # Debug print to check if module is imported
            #print(f"Module {module_name} imported successfully")

            # Dynamically get the class from the module
            plugin_class = getattr(plugin_module, object_name)

            # Create an instance of the plugin and add it to the plugins list
            self.plugins.append(plugin_class(config, utils))

        except FileNotFoundError:
            print(f"ERROR: Plugin file not found: {file_name}")
            raise
        except ImportError as e:
            print(f"ERROR: Failed to import module {module_name}: {e}")
            raise
        except AttributeError as e:
            print(f"ERROR: Class {object_name} not found in module {module_name}: {e}")
            raise
        except Exception as e:
            print(f"ERROR: Unexpected error while loading plugin '{plugin_name}': {e}")
            raise RuntimeError(
                f"ERROR: CMock unable to load plugin '{plugin_name}' '{object_name}' {file_name}"
            ) from e