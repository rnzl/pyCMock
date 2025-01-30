# =========================================================================
#   pyCMock - Automatic Mock Generation for C
#   
#   Copyright (c) 2025 Christian Renzel
#   SPDX-License-Identifier: MIT
# =========================================================================

class CMockGeneratorUtils:
    def __init__(self, config, helpers=None):
        if helpers is None:
            helpers = {}
        self.config = config
        self.ptr_handling = self.config.options['when_ptr']
        self.ordered = self.config.enforce_strict_ordering
        self.arrays = 'array' in self.config.options['plugins']
        self.cexception = 'cexception' in self.config.options['plugins']
        self.expect_any = 'expect_any_args' in self.config.options['plugins']
        self.return_thru_ptr = 'return_thru_ptr' in self.config.options['plugins']
        self.ignore_arg = 'ignore_arg' in self.config.options['plugins']
        self.ignore = 'ignore' in self.config.options['plugins']
        self.ignore_stateless = 'ignore_stateless' in self.config.options['plugins']
        self.treat_as = self.config.treat_as
        self.helpers = helpers

    @staticmethod
    def arg_type_with_const(arg):
        # Restore any "const" that was removed in header parsing
        if '*' in arg['type']:
            return f"{arg['type']} const" if arg.get('const_ptr?') else arg['type']
        else:
            return f"const {arg['type']}" if arg.get('const?') else arg['type']

    def code_verify_an_arg_expectation(self, function, arg):
        if self.arrays:
            if self.ptr_handling == 'smart':
                return self.code_verify_an_arg_expectation_with_smart_arrays(function, arg)
            elif self.ptr_handling == 'compare_data':
                return self.code_verify_an_arg_expectation_with_normal_arrays(function, arg)
            elif self.ptr_handling == 'compare_ptr':
                raise Exception("ERROR: the array plugin doesn't enjoy working with :compare_ptr only. Disable one option.")
        else:
            return self.code_verify_an_arg_expectation_with_no_arrays(function, arg)

    def code_add_base_expectation(self, func_name, global_ordering_supported=True):
        lines = f"  CMOCK_MEM_INDEX_TYPE cmock_guts_index = CMock_Guts_MemNew(sizeof(CMOCK_{func_name}_CALL_INSTANCE));\n"
        lines += f"  CMOCK_{func_name}_CALL_INSTANCE* cmock_call_instance = (CMOCK_{func_name}_CALL_INSTANCE*)CMock_Guts_GetAddressFor(cmock_guts_index);\n"
        lines += "  UNITY_TEST_ASSERT_NOT_NULL(cmock_call_instance, cmock_line, CMockStringOutOfMemory);\n"
        lines += "  memset(cmock_call_instance, 0, sizeof(*cmock_call_instance));\n"
        lines += f"  Mock.{func_name}_CallInstance = CMock_Guts_MemChain(Mock.{func_name}_CallInstance, cmock_guts_index);\n"
        if self.ignore or self.ignore_stateless:
            lines += f"  Mock.{func_name}_IgnoreBool = (char)0;\n"
        lines += "  cmock_call_instance->LineNumber = cmock_line;\n"
        if self.ordered and global_ordering_supported:
            lines += "  cmock_call_instance->CallOrder = ++GlobalExpectCount;\n"
        if self.cexception:
            lines += "  cmock_call_instance->ExceptionToThrow = CEXCEPTION_NONE;\n"
        if self.expect_any:
            lines += "  cmock_call_instance->ExpectAnyArgsBool = (char)0;\n"
        return lines

    def code_add_an_arg_expectation(self, arg, depth=1):
        lines = self.code_assign_argument_quickly(f"cmock_call_instance->Expected_{arg['name']}", arg)
        if self.arrays and isinstance(depth, str):
            lines += f"  cmock_call_instance->Expected_{arg['name']}_Depth = {arg['name']}_Depth;\n"
        if self.ignore_arg:
            lines += f"  cmock_call_instance->IgnoreArg_{arg['name']} = 0;\n"
        if self.return_thru_ptr and self.ptr_or_str(arg['type']) and not arg.get('const?'):
            lines += f"  cmock_call_instance->ReturnThruPtr_{arg['name']}_Used = 0;\n"
        return lines

    def code_assign_argument_quickly(self, dest, arg):
        if arg.get('ptr?') or arg['type'] in self.treat_as:
            return f"  {dest} = {arg['name']};\n"
        else:
            assert_expr = f"sizeof({arg['name']}) == sizeof({arg['type']}) ? 1 : -1"
            comment = "/* add {arg['type']} to :treat_as_array if this causes an error */"
            return f"  memcpy((void*)(&{dest}), (void*)(&{arg['name']}),\n" \
                   f"         sizeof({arg['type']}[{assert_expr}])); {comment}\n"

    def code_add_argument_loader(self, function):
        if function['args_string'] == 'void':
            return ''

        if self.arrays:
            args_string = ', '.join(
                [f"{self.arg_type_with_const(m)} {m['name']}, int {m['name']}_Depth" if m.get('ptr?') else f"{self.arg_type_with_const(m)} {m['name']}" for m in function['args']]
            )
            function_signature = f"void CMockExpectParameters_{function['name']}(CMOCK_{function['name']}_CALL_INSTANCE* cmock_call_instance, {args_string});\n"
            function_body = f"void CMockExpectParameters_{function['name']}(CMOCK_{function['name']}_CALL_INSTANCE* cmock_call_instance, {args_string})\n{{\n"
            function_body += ''.join(
                [self.code_add_an_arg_expectation(arg, f"{arg['name']}_Depth" if arg.get('ptr?') else 1) for arg in function['args']]
            )
            function_body += "}\n\n"
        else:
            function_signature = f"void CMockExpectParameters_{function['name']}(CMOCK_{function['name']}_CALL_INSTANCE* cmock_call_instance, {function['args_string']});\n"
            function_body = f"void CMockExpectParameters_{function['name']}(CMOCK_{function['name']}_CALL_INSTANCE* cmock_call_instance, {function['args_string']})\n{{\n"
            function_body += ''.join(
                [self.code_add_an_arg_expectation(arg) for arg in function['args']]
            )
            function_body += "}\n\n"

        return function_signature + function_body

    def code_call_argument_loader(self, function):
        if function['args_string'] != 'void':
            args = []
            for m in function['args']:
                if self.arrays and m.get('ptr?') and not m.get('array_data?'):
                    args.append(f"{m['name']}, 1")
                elif self.arrays and m.get('array_size?'):
                    args.append(f"{m['name']}, {m['name']}")
                else:
                    args.append(m['name'])
            return f"  CMockExpectParameters_{function['name']}(cmock_call_instance, {', '.join(args)});\n"
        else:
            return ''

    def ptr_or_str(self, arg_type):
        return '*' in arg_type or '*' in self.treat_as.get(arg_type, '')

    def lookup_expect_type(self, _function, arg):
        c_type = arg['type']
        arg_name = arg['name']
        expected = f"cmock_call_instance->Expected_{arg_name}"
        ignore = f"cmock_call_instance->IgnoreArg_{arg_name}"
        if arg.get('ptr?') and ('**' in c_type or self.ptr_handling == 'compare_ptr'):
            unity_func = ['UNITY_TEST_ASSERT_EQUAL_PTR', '']
        else:
            unity_func = self.helpers.get('unity_helper').get_helper(c_type) if self.helpers and 'unity_helper' in self.helpers else ['UNITY_TEST_ASSERT_EQUAL', '']
        return [c_type, arg_name, expected, ignore, unity_func[0], unity_func[1]]

    def code_verify_an_arg_expectation_with_no_arrays(self, function, arg):
        c_type, arg_name, expected, ignore, unity_func, pre = self.lookup_expect_type(function, arg)
        lines = ''
        if self.ignore_arg:
            lines += f"  if (!{ignore})\n"
        lines += "  {\n"
        lines += f"    UNITY_SET_DETAILS(CMockString_{function['name']},CMockString_{arg_name});\n"
        if unity_func == 'UNITY_TEST_ASSERT_EQUAL_MEMORY':
            c_type_local = c_type.rstrip('*')
            lines += f"    UNITY_TEST_ASSERT_EQUAL_MEMORY((void*)({pre}{expected}), (void*)({pre}{arg_name}), sizeof({c_type_local}), cmock_line, CMockStringMismatch);\n"
        elif unity_func == 'UNITY_TEST_ASSERT_EQUAL_MEMORY_ARRAY':
            if pre == '&':
                lines += f"    UNITY_TEST_ASSERT_EQUAL_MEMORY((void*)({pre}{expected}), (void*)({pre}{arg_name}), sizeof({c_type.rstrip('*')}), cmock_line, CMockStringMismatch);\n"
            else:
                lines += f"    if ({pre}{expected} == NULL)\n"
                lines += f"      {{ UNITY_TEST_ASSERT_NULL({pre}{arg_name}, cmock_line, CMockStringExpNULL); }}\n"
                lines += f"    else\n"
                lines += f"      {{ UNITY_TEST_ASSERT_EQUAL_MEMORY((void*)({pre}{expected}), (void*)({pre}{arg_name}), sizeof({c_type.rstrip('*')}), cmock_line, CMockStringMismatch); }}\n"
        elif '_ARRAY' in unity_func:
            if pre == '&':
                lines += f"    {unity_func}({pre}{expected}, {pre}{arg_name}, 1, cmock_line, CMockStringMismatch);\n"
            else:
                lines += f"    if ({pre}{expected} == NULL)\n"
                lines += f"      {{ UNITY_TEST_ASSERT_NULL({pre}{arg_name}, cmock_line, CMockStringExpNULL); }}\n"
                lines += f"    else\n"
                lines += f"      {{ {unity_func}({pre}{expected}, {pre}{arg_name}, 1, cmock_line, CMockStringMismatch); }}\n"
        else:
            lines += f"    {unity_func}({pre}{expected}, {pre}{arg_name}, cmock_line, CMockStringMismatch);\n"
        lines += "  }\n"
        return lines

    def code_verify_an_arg_expectation_with_normal_arrays(self, function, arg):
        c_type, arg_name, expected, ignore, unity_func, pre = self.lookup_expect_type(function, arg)
        depth_name = f"cmock_call_instance->Expected_{arg_name}_Depth" if arg.get('ptr?') else 1
        lines = ''
        if self.ignore_arg:
            lines += f"  if (!{ignore})\n"
        lines += "  {\n"
        lines += f"    UNITY_SET_DETAILS(CMockString_{function['name']},CMockString_{arg_name});\n"
        if unity_func == 'UNITY_TEST_ASSERT_EQUAL_MEMORY':
            c_type_local = c_type.rstrip('*')
            lines += f"    UNITY_TEST_ASSERT_EQUAL_MEMORY((void*)({pre}{expected}), (void*)({pre}{arg_name}), sizeof({c_type_local}), cmock_line, CMockStringMismatch);\n"
        elif unity_func == 'UNITY_TEST_ASSERT_EQUAL_MEMORY_ARRAY':
            if pre == '&':
                lines += f"    UNITY_TEST_ASSERT_EQUAL_MEMORY((void*)({pre}{expected}), (void*)({pre}{arg_name}), sizeof({c_type.rstrip('*')}), cmock_line, CMockStringMismatch);\n"
            else:
                lines += f"    if ({pre}{expected} == NULL)\n"
                lines += f"      {{ UNITY_TEST_ASSERT_NULL({pre}{arg_name}, cmock_line, CMockStringExpNULL); }}\n"
                lines += f"    else\n"
                lines += f"      {{ UNITY_TEST_ASSERT_EQUAL_MEMORY_ARRAY((void*)({pre}{expected}), (void*)({pre}{arg_name}), sizeof({c_type.rstrip('*')}), {depth_name}, cmock_line, CMockStringMismatch); }}\n"
        elif '_ARRAY' in unity_func:
            if pre == '&':
                lines += f"    {unity_func}({pre}{expected}, {pre}{arg_name}, {depth_name}, cmock_line, CMockStringMismatch);\n"
            else:
                lines += f"    if ({pre}{expected} == NULL)\n"
                lines += f"      {{ UNITY_TEST_ASSERT_NULL({pre}{arg_name}, cmock_line, CMockStringExpNULL); }}\n"
                lines += f"    else\n"
                lines += f"      {{ {unity_func}({pre}{expected}, {pre}{arg_name}, {depth_name}, cmock_line, CMockStringMismatch); }}\n"
        else:
            lines += f"    {unity_func}({pre}{expected}, {pre}{arg_name}, cmock_line, CMockStringMismatch);\n"
        lines += "  }\n"
        return lines

    def code_verify_an_arg_expectation_with_smart_arrays(self, function, arg):
        c_type, arg_name, expected, ignore, unity_func, pre = self.lookup_expect_type(function, arg)
        depth_name = f"cmock_call_instance->Expected_{arg_name}_Depth" if arg.get('ptr?') else 1
        lines = ''
        if self.ignore_arg:
            lines += f"  if (!{ignore})\n"
        lines += "  {\n"
        lines += f"    UNITY_SET_DETAILS(CMockString_{function['name']},CMockString_{arg_name});\n"
        if unity_func == 'UNITY_TEST_ASSERT_EQUAL_MEMORY':
            c_type_local = c_type.rstrip('*')
            lines += f"    UNITY_TEST_ASSERT_EQUAL_MEMORY((void*)({pre}{expected}), (void*)({pre}{arg_name}), sizeof({c_type_local}), cmock_line, CMockStringMismatch);\n"
        elif unity_func == 'UNITY_TEST_ASSERT_EQUAL_MEMORY_ARRAY':
            if pre == '&':
                lines += f"    UNITY_TEST_ASSERT_EQUAL_MEMORY_ARRAY((void*)({pre}{expected}), (void*)({pre}{arg_name}), sizeof({c_type.rstrip('*')}), {depth_name}, cmock_line, CMockStringMismatch);\n"
            else:
                lines += f"    if ({pre}{expected} == NULL)\n"
                lines += f"      {{ UNITY_TEST_ASSERT_NULL({arg_name}, cmock_line, CMockStringExpNULL); }}\n"
                if depth_name != 1:
                    lines += f"    else if ({depth_name} == 0)\n      {{ UNITY_TEST_ASSERT_EQUAL_PTR({pre}{expected}, {pre}{arg_name}, cmock_line, CMockStringMismatch); }}\n"
                lines += f"    else\n"
                lines += f"      {{ UNITY_TEST_ASSERT_EQUAL_MEMORY_ARRAY((void*)({pre}{expected}), (void*)({pre}{arg_name}), sizeof({c_type.rstrip('*')}), {depth_name}, cmock_line, CMockStringMismatch); }}\n"
        elif '_ARRAY' in unity_func:
            if pre == '&':
                lines += f"    {unity_func}({pre}{expected}, {pre}{arg_name}, {depth_name}, cmock_line, CMockStringMismatch);\n"
            else:
                lines += f"    if ({pre}{expected} == NULL)\n"
                lines += f"      {{ UNITY_TEST_ASSERT_NULL({pre}{arg_name}, cmock_line, CMockStringExpNULL); }}\n"
                if depth_name != 1:
                    lines += f"    else if ({depth_name} == 0)\n      {{ UNITY_TEST_ASSERT_EQUAL_PTR({pre}{expected}, {pre}{arg_name}, cmock_line, CMockStringMismatch); }}\n"
                lines += f"    else\n"
                lines += f"      {{ {unity_func}({pre}{expected}, {pre}{arg_name}, {depth_name}, cmock_line, CMockStringMismatch); }}\n"
        else:
            lines += f"    {unity_func}({pre}{expected}, {pre}{arg_name}, cmock_line, CMockStringMismatch);\n"
        lines += "  }\n"
        return lines