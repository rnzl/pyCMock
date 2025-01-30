class CMockGeneratorPluginCexception:
    """
    Plugin for handling exceptions in CMock using CException.
    """
    def __init__(self, config, utils):
        self.config = config
        self.utils = utils
        self.priority = 7
        if self.config.exclude_setjmp_h:
            raise Exception("Error: cexception is not supported without setjmp support")

    def include_files(self):
        """
        Include the CException header file.
        """
        return '#include "CException.h"\n'

    def instance_typedefs(self, _function):
        """
        Define the typedefs for instance variables.
        """
        return "  CEXCEPTION_T ExceptionToThrow;\n"

    def mock_function_declarations(self, function):
        """
        Generate mock function declarations for exceptions.
        """
        if function["args_string"] == "void":
            return (
                f"#define {function['name']}_ExpectAndThrow(cmock_to_throw) "
                f"{function['name']}_CMockExpectAndThrow(__LINE__, cmock_to_throw)\n"
                f"void {function['name']}_CMockExpectAndThrow(UNITY_LINE_TYPE cmock_line, CEXCEPTION_T cmock_to_throw);\n"
            )
        else:
            return (
                f"#define {function['name']}_ExpectAndThrow({function['args_call']}, cmock_to_throw) "
                f"{function['name']}_CMockExpectAndThrow(__LINE__, {function['args_call']}, cmock_to_throw)\n"
                f"void {function['name']}_CMockExpectAndThrow(UNITY_LINE_TYPE cmock_line, {function['args_string']}, CEXCEPTION_T cmock_to_throw);\n"
            )

    def mock_implementation(self, _function):
        """
        Generate the mock implementation for handling exceptions.
        """
        return (
            "  if (cmock_call_instance->ExceptionToThrow != CEXCEPTION_NONE)\n"
            "  {\n"
            "    UNITY_CLR_DETAILS();\n"
            "    Throw(cmock_call_instance->ExceptionToThrow);\n"
            "  }\n"
        )

    def mock_interfaces(self, function):
        """
        Generate the interface for mock functions handling exceptions.
        """
        arg_insert = "" if function["args_string"] == "void" else f"{function['args_string']}, "
        return "".join([
            f"void {function['name']}_CMockExpectAndThrow(UNITY_LINE_TYPE cmock_line, {arg_insert}CEXCEPTION_T cmock_to_throw)\n{{\n",
            self.utils.code_add_base_expectation(function["name"]),
            self.utils.code_call_argument_loader(function),
            "  cmock_call_instance->ExceptionToThrow = cmock_to_throw;\n",
            "}\n\n"
        ])
