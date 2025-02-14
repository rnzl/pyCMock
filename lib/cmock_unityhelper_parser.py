# =========================================================================
#   pyCMock - Automatic Mock Generation for C
#   
#   Copyright (c) 2025 Christian Renzel
#   SPDX-License-Identifier: MIT
# =========================================================================

import re

class CMockUnityHelperParser:
    def __init__(self, config):
        self.config = config
        self.fallback = 'UNITY_TEST_ASSERT_EQUAL_MEMORY_ARRAY' if 'array' in self.config.options[':plugins'] else 'UNITY_TEST_ASSERT_EQUAL_MEMORY'
        self.c_types = self.map_c_types()
        self.c_types.update(self.import_source())

    def get_helper(self, ctype):
        lookup = re.sub(r'(?:^|(\S?)(\s*)|(\W))const(?:$|(\s*)(\S)|(\W))', r'\1\3\5\6', ctype).strip().replace(' ', '_')
        if lookup in self.c_types:
            return [self.c_types[lookup], '']

        if lookup.endswith('*'):
            lookup = lookup.rstrip('*')
            if lookup in self.c_types:
                return [self.c_types[lookup], '*']
        else:
            lookup += '*'
            if lookup in self.c_types:
                return [self.c_types[lookup], '&']

        if re.search(r'cmock_\w+_ptr\d+', ctype):
            return ['UNITY_TEST_ASSERT_EQUAL_PTR', '']
        
        if not self.config.options[':memcmp_if_unknown']:
            raise Exception(f"Don't know how to test {ctype} and memory tests are disabled!")

        return [self.fallback, '&'] if lookup.endswith('*') else [self.fallback, '']

    def map_c_types(self):
        c_types = {}
        for ctype, expecttype in self.config.options[':treat_as'].items():
            if isinstance(ctype, str):
                c_type = ctype.replace(' ', '_')
                if '*' in expecttype:
                    c_types[c_type] = f"UNITY_TEST_ASSERT_EQUAL_{expecttype.replace('*', '')}_ARRAY"
                else:
                    c_types[c_type] = f"UNITY_TEST_ASSERT_EQUAL_{expecttype}"
                    c_types[f"{c_type}*"] = f"UNITY_TEST_ASSERT_EQUAL_{expecttype}_ARRAY"
            else:
                raise Exception(f":treat_as expects a list of identifier: identifier mappings, but got a symbol: {ctype}. Check the indentation in your project.yml")
        return c_types

    def import_source(self):
        source = self.config.load_unity_helper()
        if source is None:
            return {}

        c_types = {}
        source = re.sub(r'\/\/.*$', '', source, flags=re.MULTILINE)  # remove line comments
        source = re.sub(r'\/\*.*?\*\/', '', source, flags=re.DOTALL)  # remove block comments

        # scan for comparison helpers
        match_regex = re.compile(r"^\s*#define\s+(UNITY_TEST_ASSERT_EQUAL_(\w+))\s*\(\s*\w+\s*,\s*\w+\s*,\s*\w+\s*,\s*\w+\s*\)")
        pairs = match_regex.findall(source)
        for expect, ctype in pairs:
            if '_ARRAY' not in expect:
                c_types[ctype] = expect

        # scan for array variants of those helpers
        match_regex = re.compile(r"^\s*#define\s+(UNITY_TEST_ASSERT_EQUAL_(\w+_ARRAY))\s*\(\s*\w+\s*,\s*\w+\s*,\s*\w+\s*,\s*\w+\s*,\s*\w+\s*\)")
        pairs = match_regex.findall(source)
        for expect, ctype in pairs:
            c_types[ctype.replace('_ARRAY', '*')] = expect

        return c_types
