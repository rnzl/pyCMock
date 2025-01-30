class CMockGeneratorPluginExpect:
    """
    Plugin for generating expectation-related mock functions in CMock.
    """
    def __init__(self, config, utils):
        self.config = config
        self.ptr_handling = self.config.when_ptr
        self.ordered = self.config.enforce_strict_ordering
        self.utils = utils
        self.unity_helper = self.utils.helpers.get("unity_helper", None)
        self.priority = 5

        if self.config.plugins and ":expect_any_args" in self.config.plugins:
            self.mock_implementation = self.mock_implementation_might_check_args
        else:
            self.mock_implementation = self.mock_implementation_always_check_args

    def instance_typedefs(self, function):
        """
        Generate typedefs for mock instance variables.
        """
        lines = ""
        if not function["return"]["void?"]:
            lines += f"  {function['return']['type']} ReturnVal;\n"
        if self.ordered:
            lines += "  int CallOrder;\n"
        for arg in function["args"]:
            lines += f"  {arg['type']} Expected_{arg['name']};\n"
        return lines

    def mock_function_declarations(self, function):
        """
        Generate mock function declarations based on function signature.
        """
        if not function["args"]:
            if function["return"]["void?"]:
                return (
                    f"#define {function['name']}_ExpectAndReturn(cmock_retval) "
                    f"TEST_FAIL_MESSAGE(\"{function['name']} requires _Expect (not AndReturn)\");\n"
                    f"#define {function['name']}_Expect() {function['name']}_CMockExpect(__LINE__)\n"
                    f"void {function['name']}_CMockExpect(UNITY_LINE_TYPE cmock_line);\n"
                )
            else:
                return (
                    f"#define {function['name']}_Expect() "
                    f"TEST_FAIL_MESSAGE(\"{function['name']} requires _ExpectAndReturn\");\n"
                    f"#define {function['name']}_ExpectAndReturn(cmock_retval) "
                    f"{function['name']}_CMockExpectAndReturn(__LINE__, cmock_retval)\n"
                    f"void {function['name']}_CMockExpectAndReturn(UNITY_LINE_TYPE cmock_line, {function['return']['str']});\n"
                )
        elif function["return"]["void?"]:
            return (
                f"#define {function['name']}_ExpectAndReturn({function['args_call']}, cmock_retval) "
                f"TEST_FAIL_MESSAGE(\"{function['name']} requires _Expect (not AndReturn)\");\n"
                f"#define {function['name']}_Expect({function['args_call']}) "
                f"{function['name']}_CMockExpect(__LINE__, {function['args_call']})\n"
                f"void {function['name']}_CMockExpect(UNITY_LINE_TYPE cmock_line, {function['args_string']});\n"
            )
        else:
            return (
                f"#define {function['name']}_Expect({function['args_call']}) "
                f"TEST_FAIL_MESSAGE(\"{function['name']} requires _ExpectAndReturn\");\n"
                f"#define {function['name']}_ExpectAndReturn({function['args_call']}, cmock_retval) "
                f"{function['name']}_CMockExpectAndReturn(__LINE__, {function['args_call']}, cmock_retval)\n"
                f"void {function['name']}_CMockExpectAndReturn(UNITY_LINE_TYPE cmock_line, {function['args_string']}, {function['return']['str']});\n"
            )

    def mock_implementation_always_check_args(self, function):
        """
        Always verify arguments in the mock implementation.
        """
        lines = ""
        for arg in function["args"]:
            lines += self.utils.code_verify_an_arg_expectation(function, arg)
        return lines

    def mock_implementation_might_check_args(self, function):
        """
        Optionally verify arguments in the mock implementation based on configuration.
        """
        if not function["args"]:
            return ""

        lines = "  if (!cmock_call_instance->ExpectAnyArgsBool)\n  {\n"
        for arg in function["args"]:
            lines += self.utils.code_verify_an_arg_expectation(function, arg)
        lines += "  }\n"
        return lines

    def mock_interfaces(self, function):
        """
        Generate mock interfaces for setting up expectations.
        """
        lines = ""
        func_name = function["name"]
        if function["return"]["void?"]:
            if function["args_string"] == "void":
                lines += f"void {func_name}_CMockExpect(UNITY_LINE_TYPE cmock_line)\n{{\n"
            else:
                lines += f"void {func_name}_CMockExpect(UNITY_LINE_TYPE cmock_line, {function['args_string']})\n{{\n"
        elif function["args_string"] == "void":
            lines += f"void {func_name}_CMockExpectAndReturn(UNITY_LINE_TYPE cmock_line, {function['return']['str']})\n{{\n"
        else:
            lines += f"void {func_name}_CMockExpectAndReturn(UNITY_LINE_TYPE cmock_line, {function['args_string']}, {function['return']['str']})\n{{\n"

        lines += self.utils.code_add_base_expectation(func_name)
        lines += self.utils.code_call_argument_loader(function)
        if not function["return"]["void?"]:
            lines += self.utils.code_assign_argument_quickly("cmock_call_instance->ReturnVal", function["return"])
        lines += "}\n\n"
        return lines

    def mock_verify(self, function):
        """
        Verify that all expected calls have been made.
        """
        return (
            "  if (CMOCK_GUTS_NONE != call_instance)\n"
            "  {\n"
            f"    UNITY_SET_DETAIL(CMockString_{function['name']});\n"
            "    UNITY_TEST_FAIL(cmock_line, CMockStringCalledLess);\n"
            "  }\n"
        )
