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
        self.prefix = config.options[':mock_prefix']
        self.suffix = config.options[':mock_suffix']
        self.weak = config.options[':weak']
        self.include_inline = config.options[':treat_inlines']
        self.ordered = config.options[':enforce_strict_ordering']
        self.framework = config.options[':framework']
        self.fail_on_unexpected_calls = config.options[':fail_on_unexpected_calls']
        self.exclude_setjmp_h = config.options[':exclude_setjmp_h']
        self.subdir = config.options[':subdir']

        self.includes_h_pre_orig_header = self._format_includes(
            (config.options[':includes'] or []) + (config.options[':includes_h_pre_orig_header'] or [])
        )
        self.includes_h_post_orig_header = self._format_includes(config.options[':includes_h_post_orig_header'] or [])
        self.includes_c_pre_header = self._format_includes(config.options[':includes_c_pre_header'] or [])
        self.includes_c_post_header = self._format_includes(config.options[':includes_c_post_header'] or [])

        here = Path(__file__).parent
        unity_paths = [
            here / "../../unity/auto/type_sanitizer",
            here / "../vendor/unity/auto/type_sanitizer",
            here / "unity_type_sanitizer.py",
            Path(os.getenv("UNITY_DIR", "")).resolve() / "auto/type_sanitizer",
        ]

        for path in unity_paths:
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

        # Create Mock header file
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
        mockfolder = ''
        if folder and self.subdir:
            mockfolder = os.path.join(self.subdir, folder)
        elif self.subdir:
            mockfolder = self.subdir
        else:
            mockfolder = folder
        
        return mockfolder


    def _import_unity_type_sanitizer(self, path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("type_sanitizer", str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.type_sanitizer = module.TypeSanitizer()

    def _create_mock_subdir(self, mock_project):
        self.file_writer.create_subdir(mock_project["folder"])

    def _create_mock_header_file(self, mock_project):
        if self.include_inline == ":include":
            self.file_writer.create_file(
                mock_project["module_name"] + mock_project["module_ext"],
                self._write_module_inline_content,
                subdir=mock_project["folder"],
                mock_project=mock_project
            )

        self.file_writer.create_file(
            mock_project["mock_name"] + mock_project["module_ext"],
            self._write_mock_header_content,
            subdir=mock_project["folder"],
            mock_project=mock_project
        )

    def _write_module_inline_content(self, file, mock_project):

        file.write(mock_project["parsed_stuff"]["normalized_source"])

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
        file.write(f"{self.config.options[':orig_header_include_fmt'] % orig_filename}\n")
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
        
        # Additional content generation logic can be added here
        self._create_source_header_section(file, mock_project)
        self._create_instance_structure(file, mock_project)
        self._create_extern_declarations(file)
        self._create_mock_verify_function(file, mock_project)
        self._create_mock_init_function(file, mock_project)
        self._create_mock_destroy_function(file, mock_project)
        for function in mock_project['parsed_stuff']['functions']:
            self._create_mock_implementation(file, function)
            self._create_mock_interfaces(file, function)

    def _create_source_header_section(self, file, mock_project, filename=None):
        
        if "folder" in mock_project.keys() and mock_project["folder"] != None:
            header_file = os.path.join(
                mock_project["folder"],
                mock_project["module_name"] + mock_project["module_ext"]
            )
        else:
            header_file = mock_project["module_name"] + mock_project["module_ext"]

        if mock_project['parsed_stuff']['functions']:
            file.write("/* AUTOGENERATED FILE. DO NOT EDIT. */\n")
        file.write("#include <string.h>\n")
        file.write("#include <stdlib.h>\n")
        if not self.exclude_setjmp_h:
            file.write("#include <setjmp.h>\n")
        file.write("#include \"cmock.h\"\n")
        for inc in self.includes_c_pre_header:
            file.write(f"#include {inc}\n")

        if not filename:        
            file.write(f"#include \"{self.prefix}{header_file}\"\n")
        else:
            file.write(f"#include \"{filename}\"\n")
        
        for inc in self.includes_c_post_header:
            file.write(f"#include {inc}\n")
        file.write("\n")
        strs = []
        for func in mock_project['parsed_stuff']['functions']:
            strs.append(func['name'])
            for arg in func['args']:
                strs.append(arg['name'])
        for str in sorted(set(strs)):
            file.write(f"static const char* CMockString_{str} = \"{str}\";\n")
        file.write("\n")

    def _create_instance_structure(self, file, mock_project):
        functions = mock_project['parsed_stuff']['functions']
        for function in functions:
            file.write(f"typedef struct _CMOCK_{function['name']}_CALL_INSTANCE\n{{\n")
            file.write("  UNITY_LINE_TYPE LineNumber;\n")
            file.write(self.plugins.run('instance_typedefs', function))
            file.write(f"\n}} CMOCK_{function['name']}_CALL_INSTANCE;\n\n")
        file.write(f"static struct {mock_project['clean_name']}Instance\n{{\n")
        if not functions:
            file.write("  unsigned char placeHolder;\n")
        for function in functions:
            file.write(self.plugins.run('instance_structure', function))
            file.write(f"  CMOCK_MEM_INDEX_TYPE {function['name']}_CallInstance;\n")
        file.write("} Mock;\n\n")

    def _create_extern_declarations(self, file):
        if self.ordered:
            file.write("extern int GlobalExpectCount;\n")
            file.write("extern int GlobalVerifyOrder;\n")
        file.write("\n")

    def _create_mock_verify_function(self, file, mock_project):
        file.write(f"void {mock_project['clean_name']}_Verify(void)\n{{\n")
        verifications = ''.join([f"  call_instance = Mock.{function['name']}_CallInstance;\n{self.plugins.run('mock_verify', function)}" for function in mock_project['parsed_stuff']['functions'] if self.plugins.run('mock_verify', function)])
        if verifications:
            file.write("  UNITY_LINE_TYPE cmock_line = TEST_LINE_NUM;\n")
            file.write("  CMOCK_MEM_INDEX_TYPE call_instance;\n")
            file.write(verifications)
        file.write("}\n\n")

    def _create_mock_init_function(self, file, mock_project):
        file.write(f"void {mock_project['clean_name']}_Init(void)\n{{\n")
        file.write(f"  {mock_project['clean_name']}_Destroy();\n")
        file.write("}\n\n")

    def _create_mock_destroy_function(self, file, mock_project):
        file.write(f"void {mock_project['clean_name']}_Destroy(void)\n{{\n")
        file.write("  CMock_Guts_MemFreeAll();\n")
        file.write("  memset(&Mock, 0, sizeof(Mock));\n")
        file.write(''.join([self.plugins.run('mock_destroy', function) for function in mock_project['parsed_stuff']['functions']]))
        if not self.fail_on_unexpected_calls:
            file.write(''.join([self.plugins.run('mock_ignore', function) for function in mock_project['parsed_stuff']['functions']]))
        if self.ordered:
            file.write("  GlobalExpectCount = 0;\n")
            file.write("  GlobalVerifyOrder = 0;\n")
        file.write("}\n\n")

    def _create_mock_implementation(self, file, function):
        function_mod_and_rettype = f"{function['modifier']} {function['return']['type']}" if function['modifier'] else function['return']['type']
        if 'c_calling_convention' in function.keys() and function['c_calling_convention'] != None:
            function_mod_and_rettype += f" {function['c_calling_convention']}"
        args_string = function['args_string']
        if 'var_arg' in function.keys() and function['var_arg'] != None:
            args_string += f", {function['var_arg']}"

        for ns in function['namespace']:
            file.write(f"namespace {ns} {{\n")

        cls_pre = f"{function['class']}::" if function['class'] else ''

        if self.weak:
            file.write("#if defined (__IAR_SYSTEMS_ICC__)\n")
            file.write(f"#pragma weak {function['unscoped_name']}\n")
            file.write("#else\n")
            file.write(f"{function_mod_and_rettype} {function['unscoped_name']}({args_string}) {self.weak};\n")
            file.write("#endif\n\n")
        file.write(f"{function_mod_and_rettype} {cls_pre}{function['unscoped_name']}({args_string})\n")
        file.write("{\n")
        file.write("  UNITY_LINE_TYPE cmock_line = TEST_LINE_NUM;\n")
        file.write(f"  CMOCK_{function['name']}_CALL_INSTANCE* cmock_call_instance;\n")
        file.write(f"  UNITY_SET_DETAIL(CMockString_{function['name']});\n")
        file.write(f"  cmock_call_instance = (CMOCK_{function['name']}_CALL_INSTANCE*)CMock_Guts_GetAddressFor(Mock.{function['name']}_CallInstance);\n")
        file.write(f"  Mock.{function['name']}_CallInstance = CMock_Guts_MemNext(Mock.{function['name']}_CallInstance);\n")
        file.write(self.plugins.run('mock_implementation_precheck', function))
        file.write("  UNITY_TEST_ASSERT_NOT_NULL(cmock_call_instance, cmock_line, CMockStringCalledMore);\n")
        file.write("  cmock_line = cmock_call_instance->LineNumber;\n")
        if self.ordered:
            file.write("  if (cmock_call_instance->CallOrder > ++GlobalVerifyOrder)\n")
            file.write("    UNITY_TEST_FAIL(cmock_line, CMockStringCalledEarly);\n")
            file.write("  if (cmock_call_instance->CallOrder < GlobalVerifyOrder)\n")
            file.write("    UNITY_TEST_FAIL(cmock_line, CMockStringCalledLate);\n")
        file.write(self.plugins.run('mock_implementation', function))
        file.write("  UNITY_CLR_DETAILS();\n")
        if not function['return']['void?']:
            file.write("  return cmock_call_instance->ReturnVal;\n")
        file.write("}\n")

        for ns in function['namespace']:
            file.write("}\n")

        file.write("\n")

    def _create_mock_interfaces(self, file, function):
        file.write(self.utils.code_add_argument_loader(function))
        file.write(self.plugins.run('mock_interfaces', function))

    def _create_function_skeleton(self, file, function, existing):
        # Prepare return value and arguments
        function_mod_and_rettype = (f"{function['modifier']} " if function['modifier'] else '') + \
                                function['return']['type'] + \
                                (f" {function['c_calling_convention']}" if 'c_calling_convention' in function and function['c_calling_convention'] else '')
        args_string = function['args_string']
        if 'var_arg' in function and function['var_arg'] is not None:
            args_string += f", {function['var_arg']}"

        decl = f"{function_mod_and_rettype} {function['name']}({args_string})"

        if decl in existing:
            return

        file.write(f"{decl}\n")
        file.write("{\n")
        file.write("  /*TODO: Implement Haha Me!*/\n")
        for arg in function['args']:
            file.write(f"  (void){arg['name']};\n")
        if not function['return']['void?']:
            file.write(f"  return ({function['return']['type']})0;\n")
        file.write("}\n\n")

    def _create_skeleton_source_file(self, mock_project):
        filename = f"{self.config.options[':mock_path']}/{self.subdir + '/' if self.subdir else ''}{mock_project['module_name']}.c"
        existing = ''
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                existing = f.read()

        self.file_writer.create_file(
            f"{mock_project['module_name']}.c",
            self._write_skeleton_file,
            subdir=self.subdir, 
            mock_project=mock_project,
            existing=existing
            )

    def _write_skeleton_file(self, file, mock_project, existing):
        blank_project = mock_project.copy()
        blank_project['parsed_stuff'] = {'functions': []}
        if not existing:
            self._create_source_header_section(file, blank_project, filename=f"{mock_project['module_name']}.h")
        else:
            file.write(existing)
            if existing[-1] != "\n":
                file.write("\n")
        for function in mock_project['parsed_stuff']['functions']:
            self._create_function_skeleton(file, function, existing)
