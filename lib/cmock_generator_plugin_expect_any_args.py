class CMockGeneratorPluginExpectAnyArgs:
    """
    Plugin for generating mocks with "ExpectAnyArgs" behavior in CMock.
    """
    def __init__(self, config, utils):
        self.config = config
        self.utils = utils
        self.priority = 3

    def instance_typedefs(self, _function):
        """
        Generate typedefs for handling the "ExpectAnyArgs" flag in mock instances.
        """
        return "  char ExpectAnyArgsBool;\n"

    def mock_function_declarations(self, function):
        """
        Generate mock function declarations for "ExpectAnyArgs".
        """
        if not function["args"]:
            return ""

        if function["return"]["void?"]:
            return (
                f"#define {function['name']}_ExpectAnyArgsAndReturn(cmock_retval) "
                f"TEST_FAIL_MESSAGE(\"{function['name']} requires _ExpectAnyArgs (not AndReturn)\");\n"
                f"#define {function['name']}_ExpectAnyArgs() {function['name']}_CMockExpectAnyArgs(__LINE__)\n"
                f"void {function['name']}_CMockExpectAnyArgs(UNITY_LINE_TYPE cmock_line);\n"
            )
        else:
            return (
                f"#define {function['name']}_ExpectAnyArgs() "
                f"TEST_FAIL_MESSAGE(\"{function['name']} requires _ExpectAnyArgsAndReturn\");\n"
                f"#define {function['name']}_ExpectAnyArgsAndReturn(cmock_retval) "
                f"{function['name']}_CMockExpectAnyArgsAndReturn(__LINE__, cmock_retval)\n"
                f"void {function['name']}_CMockExpectAnyArgsAndReturn(UNITY_LINE_TYPE cmock_line, {function['return']['str']});\n"
            )

    def mock_interfaces(self, function):
        """
        Generate mock interfaces for handling "ExpectAnyArgs".
        """
        lines = ""
        if function["args"]:
            if function["return"]["void?"]:
                lines += f"void {function['name']}_CMockExpectAnyArgs(UNITY_LINE_TYPE cmock_line)\n{{\n"
            else:
                lines += f"void {function['name']}_CMockExpectAnyArgsAndReturn(UNITY_LINE_TYPE cmock_line, {function['return']['str']})\n{{\n"

            # Add base expectation with "ExpectAnyArgs" enabled
            lines += self.utils.code_add_base_expectation(function["name"], True)

            if not function["return"]["void?"]:
                lines += "  cmock_call_instance->ReturnVal = cmock_to_return;\n"

            # Set the "ExpectAnyArgs" flag
            lines += "  cmock_call_instance->ExpectAnyArgsBool = (char)1;\n"
            lines += "}\n\n"

        return lines
