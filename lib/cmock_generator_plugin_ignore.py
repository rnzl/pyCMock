class CMockGeneratorPluginIgnore:
    """
    Plugin for generating "Ignore" functionality in CMock.
    """
    def __init__(self, config, utils):
        self.config = config
        self.utils = utils
        self.priority = 2

    def instance_structure(self, function):
        """
        Generate instance structure entries for ignore behavior.
        """
        if function["return"]["void?"]:
            return f"  char {function['name']}_IgnoreBool;\n"
        else:
            return (
                f"  char {function['name']}_IgnoreBool;\n"
                f"  {function['return']['type']} {function['name']}_FinalReturn;\n"
            )

    def mock_function_declarations(self, function):
        """
        Generate mock function declarations for ignore functionality.
        """
        if function["return"]["void?"]:
            lines = (
                f"\n#define {function['name']}_IgnoreAndReturn(cmock_retval) "
                f"TEST_FAIL_MESSAGE(\"{function['name']} requires _Ignore (not AndReturn)\");\n"
                f"#define {function['name']}_Ignore() {function['name']}_CMockIgnore()\n"
                f"void {function['name']}_CMockIgnore(void);\n"
            )
        else:
            lines = (
                f"\n#define {function['name']}_Ignore() "
                f"TEST_FAIL_MESSAGE(\"{function['name']} requires _IgnoreAndReturn\");\n"
                f"#define {function['name']}_IgnoreAndReturn(cmock_retval) "
                f"{function['name']}_CMockIgnoreAndReturn(__LINE__, cmock_retval)\n"
                f"void {function['name']}_CMockIgnoreAndReturn(UNITY_LINE_TYPE cmock_line, {function['return']['str']});\n"
            )

        lines += (
            f"#define {function['name']}_StopIgnore() {function['name']}_CMockStopIgnore()\n"
            f"void {function['name']}_CMockStopIgnore(void);\n"
        )
        return lines

    def mock_implementation_precheck(self, function):
        """
        Generate the precheck implementation for mock functions with ignore behavior.
        """
        lines = f"  if (Mock.{function['name']}_IgnoreBool)\n  {{\n"
        lines += "    UNITY_CLR_DETAILS();\n"
        if function["return"]["void?"]:
            lines += "    return;\n  }\n"
        else:
            retval = {**function["return"], "name": "cmock_call_instance->ReturnVal"}
            lines += (
                f"    if (cmock_call_instance == NULL)\n"
                f"      return Mock.{function['name']}_FinalReturn;\n"
            )
            lines += self.utils.code_assign_argument_quickly(
                f"Mock.{function['name']}_FinalReturn", retval
            )
            lines += "    return cmock_call_instance->ReturnVal;\n  }\n"
        return lines

    def mock_interfaces(self, function):
        """
        Generate the mock interface implementations for ignore functionality.
        """
        lines = ""
        if function["return"]["void?"]:
            lines += f"void {function['name']}_CMockIgnore(void)\n{{\n"
        else:
            lines += (
                f"void {function['name']}_CMockIgnoreAndReturn(UNITY_LINE_TYPE cmock_line, "
                f"{function['return']['str']})\n{{\n"
            )
            lines += self.utils.code_add_base_expectation(function["name"], False)
            lines += "  cmock_call_instance->ReturnVal = cmock_to_return;\n"

        lines += f"  Mock.{function['name']}_IgnoreBool = (char)1;\n"
        lines += "}\n\n"

        # Add stop ignore implementation
        lines += f"void {function['name']}_CMockStopIgnore(void)\n{{\n"
        if not function["return"]["void?"]:
            lines += (
                f"  if(Mock.{function['name']}_IgnoreBool)\n"
                f"    Mock.{function['name']}_CallInstance = "
                f"CMock_Guts_MemNext(Mock.{function['name']}_CallInstance);\n"
            )
        lines += f"  Mock.{function['name']}_IgnoreBool = (char)0;\n"
        lines += "}\n\n"
        return lines

    def mock_ignore(self, function):
        """
        Generate code to enable ignore functionality.
        """
        return f"  Mock.{function['name']}_IgnoreBool = (char) 1;\n"

    def mock_verify(self, function):
        """
        Generate verification logic for ignore functionality.
        """
        return (
            f"  if (Mock.{function['name']}_IgnoreBool)\n"
            f"    call_instance = CMOCK_GUTS_NONE;\n"
        )
