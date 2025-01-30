class CMockGeneratorPluginIgnoreStateless:
    """
    Plugin for generating stateless "Ignore" functionality in CMock.
    """
    def __init__(self, config, utils):
        self.config = config
        self.utils = utils
        self.priority = 2

    def instance_structure(self, function):
        """
        Generate the instance structure for stateless ignore functionality.
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
        Generate mock function declarations.
        """
        if function["return"]["void?"]:
            lines = (
                f"#define {function['name']}_IgnoreAndReturn(cmock_retval) "
                f'TEST_FAIL_MESSAGE("{function["name"]} requires _Ignore (not AndReturn)");\n'
                f"#define {function['name']}_Ignore() {function['name']}_CMockIgnore()\n"
                f"void {function['name']}_CMockIgnore(void);\n"
            )
        else:
            lines = (
                f"#define {function['name']}_Ignore() "
                f'TEST_FAIL_MESSAGE("{function["name"]} requires _IgnoreAndReturn");\n'
                f"#define {function['name']}_IgnoreAndReturn(cmock_retval) "
                f"{function['name']}_CMockIgnoreAndReturn(cmock_retval)\n"
                f"void {function['name']}_CMockIgnoreAndReturn({function['return']['str']});\n"
            )
        # Add stop ignore function
        lines += (
            f"#define {function['name']}_StopIgnore() {function['name']}_CMockStopIgnore()\n"
            f"void {function['name']}_CMockStopIgnore(void);\n"
        )
        return lines

    def mock_implementation_precheck(self, function):
        """
        Add pre-check logic to handle stateless ignore functionality.
        """
        lines = f"  if (Mock.{function['name']}_IgnoreBool)\n  {{\n"
        lines += "    UNITY_CLR_DETAILS();\n"
        if function["return"]["void?"]:
            lines += "    return;\n  }\n"
        else:
            retval = function["return"].copy()
            retval["name"] = "cmock_call_instance->ReturnVal"
            lines += (
                f"    if (cmock_call_instance == NULL)\n"
                f"      return Mock.{function['name']}_FinalReturn;\n"
            )
            if not retval["void?"]:
                lines += f"  {self.utils.code_assign_argument_quickly(f'Mock.{function['name']}_FinalReturn', retval)}"
            lines += "    return cmock_call_instance->ReturnVal;\n  }\n"
        return lines

    def mock_interfaces(self, function):
        """
        Generate mock interface functions.
        """
        lines = []
        if function["return"]["void?"]:
            lines.append(f"void {function['name']}_CMockIgnore(void)\n{{\n")
        else:
            lines.append(
                f"void {function['name']}_CMockIgnoreAndReturn({function['return']['str']})\n{{\n"
            )
            lines.append(f"  Mock.{function['name']}_CallInstance = CMOCK_GUTS_NONE;\n")
            lines.append(f"  Mock.{function['name']}_FinalReturn = cmock_to_return;\n")
        lines.append(f"  Mock.{function['name']}_IgnoreBool = (char)1;\n")
        lines.append("}\n\n")

        # Stop ignore function
        lines.append(f"void {function['name']}_CMockStopIgnore(void)\n{{\n")
        lines.append(f"  Mock.{function['name']}_IgnoreBool = (char)0;\n")
        lines.append("}\n\n")

        return "".join(lines)

    def mock_ignore(self, function):
        """
        Generate code to mark a function as ignored.
        """
        return f"  Mock.{function['name']}_IgnoreBool = (char)1;\n"

    def mock_verify(self, function):
        """
        Generate code to verify a function's ignore state.
        """
        return (
            f"  if (Mock.{function['name']}_IgnoreBool)\n"
            f"    call_instance = CMOCK_GUTS_NONE;\n"
        )
