class CMockGeneratorPluginReturnThruPtr:
    """
    Plugin for handling return-through-pointer functionality in CMock.
    """
    def __init__(self, config, utils):
        self.utils = utils
        self.priority = 9
        self.config = config

    def ptr_to_const(self, arg_type):
        """
        Convert the last '*' in the type to 'const*' for type safety.
        """
        return arg_type.replace('*', ' const*', 1)

    def instance_typedefs(self, function):
        """
        Generate instance typedefs for arguments supporting return-through-pointer.
        """
        lines = []
        for arg in function['args']:
            if self.utils.ptr_or_str(arg['type']) and not arg.get('const?', False):
                lines.append(f"  char ReturnThruPtr_{arg['name']}_Used;")
                lines.append(f"  {self.ptr_to_const(arg['type'])} ReturnThruPtr_{arg['name']}_Val;")
                lines.append(f"  size_t ReturnThruPtr_{arg['name']}_Size;\n")
        return "\n".join(lines)

    def void_pointer(self, type_):
        """
        Determine if the given type is a void pointer.
        """
        if type_.lower() == 'void':
            return True
        if hasattr(self.config, 'treat_as_void'):
            return type_ in self.config.treat_as_void
        return False

    def mock_function_declarations(self, function):
        """
        Generate mock function declarations for return-through-pointer support.
        """
        lines = []
        for arg in function['args']:
            if self.utils.ptr_or_str(arg['type']) and not arg.get('const?', False):
                arg_name = arg['name']
                func_name = function['name']

                if arg['type'].endswith('*') and not self.void_pointer(arg['type'][:-1]):
                    sizeof_type = f"sizeof({arg['type'][:-1]})"
                else:
                    sizeof_type = f"sizeof(*{arg_name})"

                lines.append(
                    f"#define {func_name}_ReturnThruPtr_{arg_name}({arg_name}) "
                    f"{func_name}_CMockReturnMemThruPtr_{arg_name}(__LINE__, {arg_name}, {sizeof_type})"
                )
                lines.append(
                    f"#define {func_name}_ReturnArrayThruPtr_{arg_name}({arg_name}, cmock_len) "
                    f"{func_name}_CMockReturnMemThruPtr_{arg_name}(__LINE__, {arg_name}, (cmock_len * sizeof(*{arg_name})))"
                )
                lines.append(
                    f"#define {func_name}_ReturnMemThruPtr_{arg_name}({arg_name}, cmock_size) "
                    f"{func_name}_CMockReturnMemThruPtr_{arg_name}(__LINE__, {arg_name}, (cmock_size))"
                )
                lines.append(
                    f"void {func_name}_CMockReturnMemThruPtr_{arg_name}(UNITY_LINE_TYPE cmock_line, "
                    f"{self.ptr_to_const(arg['type'])} {arg_name}, size_t cmock_size);"
                )
        return "\n".join(lines)

    def mock_interfaces(self, function):
        """
        Generate mock interface implementations for return-through-pointer support.
        """
        lines = []
        for arg in function['args']:
            if self.utils.ptr_or_str(arg['type']) and not arg.get('const?', False):
                arg_name = arg['name']
                func_name = function['name']

                lines.append(
                    f"void {func_name}_CMockReturnMemThruPtr_{arg_name}(UNITY_LINE_TYPE cmock_line, "
                    f"{self.ptr_to_const(arg['type'])} {arg_name}, size_t cmock_size)"
                )
                lines.append("{")
                lines.append(
                    f"  CMOCK_{func_name}_CALL_INSTANCE* cmock_call_instance = "
                    f"(CMOCK_{func_name}_CALL_INSTANCE*)CMock_Guts_GetAddressFor("
                    f"CMock_Guts_MemEndOfChain(Mock.{func_name}_CallInstance));"
                )
                lines.append("  UNITY_TEST_ASSERT_NOT_NULL(cmock_call_instance, cmock_line, CMockStringPtrPreExp);")
                lines.append(f"  cmock_call_instance->ReturnThruPtr_{arg_name}_Used = 1;")
                lines.append(f"  cmock_call_instance->ReturnThruPtr_{arg_name}_Val = {arg_name};")
                lines.append(f"  cmock_call_instance->ReturnThruPtr_{arg_name}_Size = cmock_size;")
                lines.append("}\n\n")
        return "\n".join(lines)

    def mock_implementation(self, function):
        """
        Generate implementation for handling return-through-pointer values during mock execution.
        """
        lines = []
        for arg in function['args']:
            if self.utils.ptr_or_str(arg['type']) and not arg.get('const?', False):
                arg_name = arg['name']

                lines.append(f"  if (cmock_call_instance->ReturnThruPtr_{arg_name}_Used)")
                lines.append("  {")
                lines.append(f"    UNITY_TEST_ASSERT_NOT_NULL({arg_name}, cmock_line, CMockStringPtrIsNULL);")
                lines.append(f"    memcpy((void*){arg_name}, (const void*)cmock_call_instance->ReturnThruPtr_{arg_name}_Val, ")
                lines.append(f"      cmock_call_instance->ReturnThruPtr_{arg_name}_Size);")
                lines.append("  }")
        return "\n".join(lines)
