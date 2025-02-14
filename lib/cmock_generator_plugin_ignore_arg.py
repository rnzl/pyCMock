class CMockGeneratorPluginIgnoreArg:
    """
    Plugin for generating "Ignore Argument" functionality in CMock.
    """
    def __init__(self, _config, utils):
        self.utils = utils
        self.priority = 10

    def instance_typedefs(self, function):
        """
        Generate typedefs for instance structure to track ignored arguments.
        """
        lines = ""
        for arg in function["args"]:
            lines += f"  char IgnoreArg_{arg['name']};\n"
        return lines

    def mock_function_declarations(self, function):
        """
        Generate mock function declarations for ignoring arguments.
        """
        lines = ""
        for arg in function["args"]:
            lines += (
                f"#define {function['name']}_IgnoreArg_{arg['name']}() "
                f"{function['name']}_CMockIgnoreArg_{arg['name']}(__LINE__)\n"
                f"void {function['name']}_CMockIgnoreArg_{arg['name']}(UNITY_LINE_TYPE cmock_line);\n"
            )
        return lines

    def mock_interfaces(self, function):
        """
        Generate the mock interfaces for ignoring arguments.
        """
        lines = ""
        func_name = function["name"]
        for arg in function["args"]:
            lines += (
                f"void {func_name}_CMockIgnoreArg_{arg['name']}(UNITY_LINE_TYPE cmock_line)\n"
                f"{{\n"
                f"  CMOCK_{func_name}_CALL_INSTANCE* cmock_call_instance = "
                f"(CMOCK_{func_name}_CALL_INSTANCE*)CMock_Guts_GetAddressFor("
                f"CMock_Guts_MemEndOfChain(Mock.{func_name}_CallInstance));\n"
                f"  UNITY_TEST_ASSERT_NOT_NULL(cmock_call_instance, cmock_line, CMockStringIgnPreExp);\n"
                f"  cmock_call_instance->IgnoreArg_{arg['name']} = 1;\n"
                f"}}\n\n"
            )
        return lines
