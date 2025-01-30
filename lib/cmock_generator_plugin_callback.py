class CMockGeneratorPluginCallback:
    """
    Plugin for generating callback-based mocks in CMock.
    """
    def __init__(self, config, utils):
        self.config = config
        self.utils = utils
        self.priority = 6
        self.include_count = config.callback_include_count

    def instance_structure(self, function):
        """
        Generate the instance structure for the function's callback.
        """
        func_name = function["name"]
        return (
            f"  char {func_name}_CallbackBool;\n"
            f"  CMOCK_{func_name}_CALLBACK {func_name}_CallbackFunctionPointer;\n"
            f"  int {func_name}_CallbackCalls;\n"
        )

    def mock_function_declarations(self, function):
        """
        Generate mock function declarations for callbacks.
        """
        func_name = function["name"]
        return_type = function["return"]["type"]
        action = "AddCallback" if self.config.callback_after_arg_check else "Stub"
        style = (1 if self.include_count else 0) | (2 if function["args"] else 0)
        styles = [
            "void",
            "int cmock_num_calls",
            function["args_string"],
            f"{function['args_string']}, int cmock_num_calls",
        ]
        return (
            f"typedef {return_type} (* CMOCK_{func_name}_CALLBACK)({styles[style]});\n"
            f"void {func_name}_AddCallback(CMOCK_{func_name}_CALLBACK Callback);\n"
            f"void {func_name}_Stub(CMOCK_{func_name}_CALLBACK Callback);\n"
            f"#define {func_name}_StubWithCallback {func_name}_{action}\n"
        )

    def generate_call(self, function):
        """
        Generate the call to the callback function.
        """
        args = [arg["name"] for arg in function["args"]]
        if self.include_count:
            args.append(f"Mock.{function['name']}_CallbackCalls++")
        return f"Mock.{function['name']}_CallbackFunctionPointer({', '.join(args)})"

    def mock_implementation(self, function):
        """
        Generate the implementation for the callback.
        """
        func_name = function["name"]
        if function["return"]["void?"]:
            return (
                f"  if (Mock.{func_name}_CallbackFunctionPointer != NULL)\n"
                f"  {{\n"
                f"    {self.generate_call(function)};\n"
                f"  }}\n"
            )
        else:
            return (
                f"  if (Mock.{func_name}_CallbackFunctionPointer != NULL)\n"
                f"  {{\n"
                f"    cmock_call_instance->ReturnVal = {self.generate_call(function)};\n"
                f"  }}\n"
            )

    def mock_implementation_precheck(self, function):
        """
        Generate the precheck implementation for the callback.
        """
        func_name = function["name"]
        if function["return"]["void?"]:
            return (
                f"  if (!Mock.{func_name}_CallbackBool &&\n"
                f"      Mock.{func_name}_CallbackFunctionPointer != NULL)\n"
                f"  {{\n"
                f"    {self.generate_call(function)};\n"
                f"    UNITY_CLR_DETAILS();\n"
                f"    return;\n"
                f"  }}\n"
            )
        else:
            return (
                f"  if (!Mock.{func_name}_CallbackBool &&\n"
                f"      Mock.{func_name}_CallbackFunctionPointer != NULL)\n"
                f"  {{\n"
                f"    {function['return']['type']} cmock_cb_ret = {self.generate_call(function)};\n"
                f"    UNITY_CLR_DETAILS();\n"
                f"    return cmock_cb_ret;\n"
                f"  }}\n"
            )

    def mock_interfaces(self, function):
        """
        Generate the interface for setting up and stubbing the callback.
        """
        func_name = function["name"]
        has_ignore = ":ignore" in self.config.plugins
        lines = []
        lines.append(f"void {func_name}_AddCallback(CMOCK_{func_name}_CALLBACK Callback)\n{{\n")
        if has_ignore:
            lines.append(f"  Mock.{func_name}_IgnoreBool = (char)0;\n")
        lines.append(f"  Mock.{func_name}_CallbackBool = (char)1;\n")
        lines.append(f"  Mock.{func_name}_CallbackFunctionPointer = Callback;\n")
        lines.append("}\n\n")
        lines.append(f"void {func_name}_Stub(CMOCK_{func_name}_CALLBACK Callback)\n{{\n")
        if has_ignore:
            lines.append(f"  Mock.{func_name}_IgnoreBool = (char)0;\n")
        lines.append(f"  Mock.{func_name}_CallbackBool = (char)0;\n")
        lines.append(f"  Mock.{func_name}_CallbackFunctionPointer = Callback;\n")
        lines.append("}\n\n")
        return "".join(lines)

    def mock_verify(self, function):
        """
        Generate the verification code for the callback.
        """
        func_name = function["name"]
        return (
            f"  if (Mock.{func_name}_CallbackFunctionPointer != NULL)\n"
            f"  {{\n"
            f"    call_instance = CMOCK_GUTS_NONE;\n"
            f"    (void)call_instance;\n"
            f"  }}\n"
        )
