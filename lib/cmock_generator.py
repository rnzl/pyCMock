# =========================================================================
#   pyCMock - Automatic Mock Generation for C
#   
#   Copyright (c) 2025 Christian Renzel
#   SPDX-License-Identifier: MIT
# =========================================================================

import os
import re
from pathlib import Path

from io import StringIO

class CMockGenerator:
    def __init__(self, config, file_writer, utils, plugins):
        self.file_writer = file_writer
        self.utils = utils
        self.plugins = plugins
        self.config = config
        self.prefix = config.options['mock_prefix']
        self.suffix = config.options['mock_suffix']
        self.weak = config.options['weak']
        self.include_inline = config.options['treat_inlines']
        self.ordered = config.options['enforce_strict_ordering']
        self.framework = config.options['framework']
        self.fail_on_unexpected_calls = config.options['fail_on_unexpected_calls']
        self.exclude_setjmp_h = config.options['exclude_setjmp_h']
        self.subdir = config.options['subdir']

        self.includes_h_pre_orig_header = self._format_includes(
            (config.options['includes'] or []) + (config.options['includes_h_pre_orig_header'] or [])
        )
        self.includes_h_post_orig_header = self._format_includes(config.options['includes_h_post_orig_header'] or [])
        self.includes_c_pre_header = self._format_includes(config.options['includes_c_pre_header'] or [])
        self.includes_c_post_header = self._format_includes(config.options['includes_c_post_header'] or [])

        here = Path(__file__).parent
        unity_paths = [
            here / "../../unity/auto/type_sanitizer",
            here / "../vendor/unity/auto/type_sanitizer",
            here / "unity_type_sanitizer.py",
            Path(os.getenv("UNITY_DIR", "")).resolve() / "auto/type_sanitizer",
        ]

        for path in unity_paths:
            print(f"{path}")
            if path.exists():
                self._import_unity_type_sanitizer(path)
                break
        else:
            raise RuntimeError("Failed to find an instance of Unity to pull in type_sanitizer module!")

    def create_mock(self, module_name, parsed_stuff, module_ext=None, folder=None):
        mock_name = f"{self.prefix}{module_name}{self.suffix}"
        mock_folder = self._determine_mock_folder(folder)
        clean_name = self.type_sanitizer.sanitize_c_identifier(mock_name)
        mock_project = {
            "module_name": module_name,
            "module_ext": module_ext or ".h",
            "mock_name": mock_name,
            "clean_name": clean_name,
            "folder": mock_folder,
            "parsed_stuff": parsed_stuff,
            "skeleton": False,
        }
        self._create_mock_subdir(mock_project)

        # Create Mock he
        self._create_mock_header_file(mock_project)
        self._create_mock_source_file(mock_project)

    def create_skeleton(self, module_name, parsed_stuff):
        mock_project = {
            "module_name": module_name,
            "module_ext": ".h",
            "parsed_stuff": parsed_stuff,
            "skeleton": True,
        }
        self._create_skeleton_source_file(mock_project)

    def _format_includes(self, includes):
        return [
            f'"{h}"' if not h.startswith("<") else h
            for h in includes
        ]

    def _determine_mock_folder(self, folder):
        if folder and self.subdir:
            return os.path.join(self.subdir, folder)
        return self.subdir or folder

    def _import_unity_type_sanitizer(self, path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("type_sanitizer", str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.type_sanitizer = module.TypeSanitizer()

    def _create_mock_subdir(self, mock_project):
        self.file_writer.create_subdir(mock_project["folder"])

    def _create_mock_header_file(self, mock_project):
        if self.include_inline == "include":
            self.file_writer.create_file(
                mock_project["module_name"] + mock_project["module_ext"],
                mock_project["folder"],
                lambda f, _: f.write(mock_project["parsed_stuff"]["normalized_source"])
            )

        self.file_writer.create_file(
            mock_project["mock_name"] + mock_project["module_ext"],
            self._write_mock_header_content,
            subdir=mock_project["folder"],
            mock_project=mock_project
        )

    def _write_mock_header_content(self, file, mock_project):
        clean_name = mock_project["clean_name"]
        define_name = clean_name.upper()
        if mock_project["folder"]:
            orig_filename = os.path.join(
                mock_project["folder"],
                mock_project["module_name"] + mock_project["module_ext"]
            )
        else:
            orig_filename = mock_project["module_name"] + mock_project["module_ext"]
        
        file.write("/* AUTOGENERATED FILE. DO NOT EDIT. */\n")
        file.write(f"#ifndef _{define_name}_H\n")
        file.write(f"#define _{define_name}_H\n\n")
        file.write(f"#include \"{self.framework}.h\"\n")

        file.writelines([f"#include {inc}\n" for inc in self.includes_h_pre_orig_header])
        file.write(f"{self.config.options['orig_header_include_fmt'] % orig_filename}\n")
        file.writelines([f"#include {inc}\n" for inc in self.includes_h_post_orig_header])

        plugin_includes = self.plugins.run("include_files")
        if plugin_includes:
            file.write(plugin_includes)

        file.write("\n")
        file.write("/* Ignore the following warnings, since we are copying code */\n")
        file.write("#if defined(__GNUC__) && !defined(__ICC) && !defined(__TMS470__)\n")
        file.write("#if __GNUC__ > 4 || (__GNUC__ == 4 && (__GNUC_MINOR__ > 6 || (__GNUC_MINOR__ == 6 && __GNUC_PATCHLEVEL__ > 0)))\n")
        file.write("#pragma GCC diagnostic push\n")
        file.write("#endif\n")
        file.write("#if !defined(__clang__)\n")
        file.write("#pragma GCC diagnostic ignored \"-Wpragmas\"\n")
        file.write("#endif\n")
        file.write("#pragma GCC diagnostic ignored \"-Wunknown-pragmas\"\n")
        file.write("#pragma GCC diagnostic ignored \"-Wduplicate-decl-specifier\"\n")
        file.write("#endif\n")
        file.write("\n")
        file.write("#ifdef __cplusplus\nextern \"C\" {\n#endif\n\n")
        
        self._create_service_call_declarations(file, clean_name)
        self._create_typedefs(file, mock_project)

        for func in mock_project["parsed_stuff"]["functions"]:
            self._write_function_declaration(file, func)

        file.write("\n")
        file.write("#ifdef __cplusplus\n")
        file.write("}\n")
        file.write("#endif\n")
        file.write("\n")
        file.write("#if defined(__GNUC__) && !defined(__ICC) && !defined(__TMS470__)\n")
        file.write("#if __GNUC__ > 4 || (__GNUC__ == 4 && (__GNUC_MINOR__ > 6 || (__GNUC_MINOR__ == 6 && __GNUC_PATCHLEVEL__ > 0)))\n")
        file.write("#pragma GCC diagnostic pop\n")
        file.write("#endif\n")
        file.write("#endif\n")
        file.write("\n")
        file.write("#endif\n")

    def _create_typedefs(self, file, mock_project):
        file.write("\n")
        for typedef in mock_project["parsed_stuff"]["typedefs"]:
            file.write(f"{typedef}\n")
        file.write("\n\n")

    def _create_service_call_declarations(self, file, clean_name):
        file.write(f"void {clean_name}_Init(void);\n")
        file.write(f"void {clean_name}_Destroy(void);\n")
        file.write(f"void {clean_name}_Verify(void);\n\n")

    def _write_function_declaration(self, file, function):
        using_namespace = "::".join(function.get("namespace", []))
        if using_namespace:
            file.write(f"using namespace {using_namespace};\n")
        file.write(self.plugins.run("mock_function_declarations", function))

    def _create_mock_source_file(self, mock_project):
        self.file_writer.create_file(
            f"{mock_project['mock_name']}.c",
            self._write_mock_source_content,
            subdir=mock_project["folder"],
            mock_project=mock_project
        )

    def _write_mock_source_content(self, file, mock_project):
        
        if mock_project["folder"]:
            header_file = os.path.join(
                mock_project["folder"],
                mock_project["module_name"] + mock_project["module_ext"]
            )
        else:
            header_file = mock_project["module_name"] + mock_project["module_ext"]


        content = [
            "/* AUTOGENERATED FILE. DO NOT EDIT. */\n",
            "#include <string.h>\n",
            "#include <stdlib.h>\n",
        ]
        
        if not self.exclude_setjmp_h:
            content.append("#include <setjmp.h>\n")

        content.append(f"#include \"{header_file}\"\n\n")

        file.writelines(content)

        # Additional content generation logic can be added here

    def _create_skeleton_source_file(self, mock_project):
        # Implementation similar to mock source creation
        pass
