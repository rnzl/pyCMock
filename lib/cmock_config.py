# =========================================================================
#   pyCMock - Automatic Mock Generation for C
#   
#   Copyright (c) 2025 Christian Renzel
#   SPDX-License-Identifier: MIT
# =========================================================================

import yaml
import os
from pathlib import Path


class CMockConfig:
    CMOCK_DEFAULT_OPTIONS = {
        ':framework': 'unity',
        ':mock_path': 'mocks',
        ':mock_prefix': 'Mock',
        ':mock_suffix': '',
        ':skeleton_path': '',
        ':weak': '',
        ':subdir': None,
        ':plugins': [],
        ':strippables': [r'(?:__attribute__\s*\([ (]*.*?[ )]*\)+)'],
        ':attributes': ['__ramfunc', '__irq', '__fiq', 'register', 'extern'],
        ':c_calling_conventions': ['__stdcall', '__cdecl', '__fastcall'],
        ':enforce_strict_ordering': False,
        ':fail_on_unexpected_calls': True,
        ':unity_helper_path': False,
        ':treat_as': {},
        ':treat_as_array': {},
        ':treat_as_void': [],
        ':memcmp_if_unknown': True,
        ':when_no_prototypes': ':warn',  # options: ignore, warn, error
        ':when_ptr': ':compare_data',   # options: compare_ptr, compare_data, smart
        ':verbosity': 2,              # 0: errors only, 1: warnings, 2: normal, 3: verbose
        ':treat_externs': ':exclude',  # options: include, exclude
        ':treat_inlines': ':exclude',  # options: include, exclude
        ':callback_include_count': True,
        ':callback_after_arg_check': False,
        ':includes': None,
        ':includes_h_pre_orig_header': None,
        ':includes_h_post_orig_header': None,
        ':includes_c_pre_header': None,
        ':includes_c_post_header': None,
        ':orig_header_include_fmt': '#include "%s"',
        ':array_size_type': [],
        ':array_size_name': 'size|len',
        ':skeleton': False,
        ':exclude_setjmp_h': False,
        ':inline_function_patterns': [
            r'(static\s+inline|inline\s+static)\s*',
            r'(\binline\b)\s*',
            r'(?:static\s*)?(?:__inline__)?__attribute__\s*\([ (]*always_inline[ )]*\)',
            r'static __inline__'
        ]
    }

    def __init__(self, options=None):
        if options is None:
            self.options = self.CMOCK_DEFAULT_OPTIONS.copy()
        elif isinstance(options, str):
            self.options = {**self.CMOCK_DEFAULT_OPTIONS, **self.load_config_file_from_yaml(options)}
        elif isinstance(options, dict):
            self.options = {**self.CMOCK_DEFAULT_OPTIONS, **options}
        else:
            raise ValueError("Options should be a filename (str) or a dictionary (dict)")

        # Validate certain options are lists
        for opt in [':plugins', ':attributes', ':treat_as_void']:
            if not isinstance(self.options.get(opt), list):
                self.options[opt] = []
                if self.options.get(':verbosity', 2) > 0:
                    print(f"WARNING: '{opt}' should be a list.")

        for opt in [':includes', ':includes_h_pre_orig_header', ':includes_h_post_orig_header',
                    ':includes_c_pre_header', ':includes_c_post_header']:
            if self.options.get(opt) is not None and not isinstance(self.options[opt], list):
                self.options[opt] = []
                if self.options.get(':verbosity', 2) > 0:
                    print(f"WARNING: '{opt}' should be a list.")

        self.options[':unity_helper_path'] = (
            [self.options[':unity_helper_path']]
            if isinstance(self.options.get(':unity_helper_path'), str)
            else self.options.get(':unity_helper_path', [])
        )

        if self.options[':unity_helper_path']:
            self.add_unity_helper_paths_to_post_headers()

        self.options[':plugins'] = list(map(lambda x: str(x).lower(), filter(None, self.options[':plugins'])))

        if 'ignore' not in self.options[':plugins'] and not self.options[':fail_on_unexpected_calls']:
            raise ValueError("The 'ignore' plugin is required to disable 'fail_on_unexpected_calls'")

        self.options[':treat_as'] = {**self.standard_treat_as_map(), **self.options[':treat_as']}

    def load_config_file_from_yaml(self, yaml_filename):
        try:
            with open(yaml_filename, 'r') as file:
                data = yaml.safe_load(file)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file {yaml_filename}: {e}")
        
        return data.get(':cmock', {})

    def add_unity_helper_paths_to_post_headers(self):
        post_headers = self.options.get(':includes_c_post_header', [])
        helper_paths = []
        for path in self.options[':unity_helper_path']:
            try:
                rel_path = Path(os.path.abspath(path)).relative_to(
                    os.path.abspath(self.options[':mock_path'])
                ).as_posix()
                helper_paths.append(rel_path)
            except ValueError:
                helper_paths.append(path)
        self.options[':includes_c_post_header'] = list(set(post_headers + helper_paths))

    def load_unity_helper(self):
        if not self.options[':unity_helper_path']:
            return None
        content = ""
        for filename in self.options[':unity_helper_path']:
            with open(filename, 'r') as file:
                content += f"\n{file.read()}"
        return content

    def standard_treat_as_map(self):
        return {
            'int': 'INT',
            'char': 'INT8',
            'short': 'INT16',
            'long': 'INT',
            'int8': 'INT8',
            'int16': 'INT16',
            'int32': 'INT',
            'int8_t': 'INT8',
            'int16_t': 'INT16',
            'int32_t': 'INT',
            'bool': 'INT',
            'bool_t': 'INT',
            'unsigned int': 'HEX32',
            'unsigned long': 'HEX32',
            'uint32': 'HEX32',
            'uint32_t': 'HEX32',
            'void*': 'HEX8_ARRAY',
            'unsigned short': 'HEX16',
            'uint16': 'HEX16',
            'unsigned char': 'HEX8',
            'uint8': 'HEX8',
            'char*': 'STRING',
            'float': 'FLOAT',
            'double': 'FLOAT'
        }
