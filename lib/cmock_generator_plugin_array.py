class CMockGeneratorPluginArray:
    """
    Plugin for generating array-based mocks in CMock.
    """
    def __init__(self, config, utils):
        self.config = config
        self.ptr_handling = config.options[':when_ptr']
        self.ordered = config.options[':enforce_strict_ordering']
        self.utils = utils
        self.unity_helper = utils.helpers.get("unity_helper")
        self.priority = 8

    def instance_typedefs(self, function):
        """
        Generate typedefs for instances with pointer depth.
        """
        return "".join(
            f"  int Expected_{arg['name']}_Depth;\n"
            for arg in function["args"]
            if arg.get("ptr?")
        )

    def mock_function_declarations(self, function):
        """
        Generate mock function declarations.
        """
        if not function.get("contains_ptr?"):
            return ""

        args_call_i = ", ".join(
            f"{arg['name']}, {arg['name']}_Depth" if arg.get("ptr?") else arg["name"]
            for arg in function["args"]
        )
        args_call_o = ", ".join(
            f"{arg['name']}, ({arg['name']}_Depth)" if arg.get("ptr?") else arg["name"]
            for arg in function["args"]
        )
        args_string = ", ".join(
            f"{self.utils.arg_type_with_const(arg)} {arg['name']}, int {arg['name']}_Depth"
            if arg.get("ptr?")
            else f"{self.utils.arg_type_with_const(arg)} {arg['name']}"
            for arg in function["args"]
        )

        if function["return"]["void?"]:
            return (
                f"#define {function['name']}_ExpectWithArrayAndReturn({args_call_i}, cmock_retval) "
                f"TEST_FAIL_MESSAGE(\"{function['name']} requires _ExpectWithArray (not AndReturn)\");\n"
                f"#define {function['name']}_ExpectWithArray({args_call_i}) "
                f"{function['name']}_CMockExpectWithArray(__LINE__, {args_call_o})\n"
                f"void {function['name']}_CMockExpectWithArray(UNITY_LINE_TYPE cmock_line, {args_string});\n"
            )
        else:
            return (
                f"#define {function['name']}_ExpectWithArray({args_call_i}) "
                f"TEST_FAIL_MESSAGE(\"{function['name']} requires _ExpectWithArrayAndReturn\");\n"
                f"#define {function['name']}_ExpectWithArrayAndReturn({args_call_i}, cmock_retval) "
                f"{function['name']}_CMockExpectWithArrayAndReturn(__LINE__, {args_call_o}, cmock_retval)\n"
                f"void {function['name']}_CMockExpectWithArrayAndReturn(UNITY_LINE_TYPE cmock_line, {args_string}, "
                f"{function['return']['str']});\n"
            )

    def mock_interfaces(self, function):
        """
        Generate the mock interface implementation.
        """
        if not function.get("contains_ptr?"):
            return ""

        func_name = function["name"]
        args_string = ", ".join(
            f"{self.utils.arg_type_with_const(arg)} {arg['name']}, int {arg['name']}_Depth"
            if arg.get("ptr?")
            else f"{self.utils.arg_type_with_const(arg)} {arg['name']}"
            for arg in function["args"]
        )
        call_string = ", ".join(
            f"{arg['name']}, {arg['name']}_Depth" if arg.get("ptr?") else arg["name"]
            for arg in function["args"]
        )

        lines = []
        if function["return"]["void?"]:
            lines.append(
                f"void {func_name}_CMockExpectWithArray(UNITY_LINE_TYPE cmock_line, {args_string})\n"
            )
        else:
            lines.append(
                f"void {func_name}_CMockExpectWithArrayAndReturn(UNITY_LINE_TYPE cmock_line, {args_string}, "
                f"{function['return']['str']})\n"
            )

        lines.append("{\n")
        lines.append(self.utils.code_add_base_expectation(func_name))
        lines.append(
            f"  CMockExpectParameters_{func_name}(cmock_call_instance, {call_string});\n"
        )
        if not function["return"]["void?"]:
            lines.append("  cmock_call_instance->ReturnVal = cmock_to_return;\n")
        lines.append("}\n\n")

        return "".join(lines)
