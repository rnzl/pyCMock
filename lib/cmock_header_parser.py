import re

class CMockHeaderParser:
    def __init__(self, config):
        self.c_strippables = config.options[':strippables']
        self.c_attr_noconst = list(set(config.options[':attributes']) - {'const'})
        self.c_attributes = ['const'] + self.c_attr_noconst
        self.c_calling_conventions = list(set(config.options[':c_calling_conventions']))
        self.treat_as_array = config.options[':treat_as_array']
        self.treat_as_void = list(set(['void'] + config.options[':treat_as_void']))
        self.function_declaration_parse_base_match = r'([\w\s\*\(\),\[\]]*?\w[\w\s\*\(\),\[\]]*?)\(([\w\s\*\(\),\.\[\]+\-\/]*)\)'
        self.declaration_parse_matcher = re.compile(self.function_declaration_parse_base_match + r'$', re.MULTILINE)
        self.standards = list(set(['int', 'short', 'char', 'long', 'unsigned', 'signed'] + list(config.options[':treat_as'].keys())))
        self.array_size_name = config.options[':array_size_name']
        self.array_size_type = list(set(['int', 'size_t'] + config.options[':array_size_type']))
        self.when_no_prototypes = config.options[':when_no_prototypes']
        self.local_as_void = self.treat_as_void
        self.verbosity = config.options[':verbosity']
        self.treat_externs = config.options[':treat_externs']
        self.treat_inlines = config.options[':treat_inlines']
        self.inline_function_patterns = config.options[':inline_function_patterns']
        if self.treat_externs == ':include':
            self.c_strippables.append('extern')
        if self.treat_inlines == ':include':
            self.c_strippables.append('inline')

    def parse(self, name, source):
        parse_project = {
            'module_name': re.sub(r'\W', '', name),
            'typedefs': [],
            'functions': [],
            'normalized_source': None
        }

        function_names = []

        all_funcs = self.parse_functions(name, self.import_source(source, parse_project))
        all_funcs += self.parse_cpp_functions(self.import_source(source, parse_project, True))
        for decl in all_funcs:
            func = self.parse_declaration(parse_project, decl)
            if func['name'] not in function_names:
                parse_project['functions'].append(func)
                function_names.append(func['name'])

        parse_project['normalized_source'] = self.transform_inline_functions(source) if self.treat_inlines == 'include' else ''

        return {
            'includes': None,
            'functions': parse_project['functions'],
            'typedefs': parse_project['typedefs'],
            'normalized_source': parse_project['normalized_source']
        }

    def remove_comments_from_source(self, source):
        # Remove line comments that comment out the start of blocks
        source = re.sub(r'(?<!\*)\/\/(?:.+\/\*|\*(?:$|[^\/])).*$', '', source, flags=re.MULTILINE)
        # Remove block comments (including nested ones)
        source = re.sub(r'/\*.*?\*/', '', source, flags=re.DOTALL)
        # Remove line comments
        source = re.sub(r'//.*$', '', source, flags=re.MULTILINE)
        return source

    def remove_nested_pairs_of_braces(self, source):
        if int(re.split(r'\.', re.__version__)[0]) > 1:
            r = r'\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}'
            source = re.sub(r, '{ }', source, flags=re.DOTALL)
        else:
            while re.search(r'\{[^\{\}]*\{[^\{\}]*\}[^\{\}]*\}', source, flags=re.DOTALL):
                source = re.sub(r'\{[^\{\}]*\{[^\{\}]*\}[^\{\}]*\}', '{ }', source, flags=re.DOTALL)
        return source

    def count_number_of_pairs_of_braces_in_function(self, source):
        is_function_start_found = False
        curr_level = 0
        total_pairs = 0

        for c in source:
            if c == '{':
                curr_level += 1
                total_pairs += 1
                is_function_start_found = True
            elif c == '}':
                curr_level -= 1

            if is_function_start_found and curr_level == 0:
                break

        if curr_level != 0:
            total_pairs = 0

        return total_pairs

    def transform_inline_functions(self, source):
        inline_function_regex_formats = []
        square_bracket_pair_regex_format = r'\{[^\{\}]*\}'

        for user_format_string in self.inline_function_patterns:
            user_regex = re.compile(user_format_string)
            word_boundary_before_user_regex = r'\b'
            cleanup_spaces_after_user_regex = r' *\b'
            inline_function_regex_formats.append(re.compile(word_boundary_before_user_regex + user_regex.pattern + cleanup_spaces_after_user_regex))

        source = source.encode('ISO-8859-1').decode('utf-8', errors='replace')
        source = self.remove_comments_from_source(source)
        source = re.sub(r'\s*\\(\n|\s*)', ' ', source, flags=re.DOTALL)

        for format in inline_function_regex_formats:
            inspected_source = ''
            regex_matched = False
            while True:
                inline_function_match = re.search(format, source)

                if inline_function_match is None:
                    if regex_matched:
                        source = inspected_source + source
                    break

                regex_matched = True

                if re.search(r'(#define\s*)\Z', inline_function_match.pre_match):
                    stripped_pre_match = re.sub(r'(#define\s*)\Z', '', inline_function_match.pre_match)
                    stripped_post_match = re.sub(r'\A(.*\n?)', '', inline_function_match.post_match)
                    inspected_source += stripped_pre_match
                    source = stripped_post_match
                    continue

                if re.search(self.function_declaration_parse_base_match + r'\s*;', inline_function_match.post_match, flags=re.MULTILINE):
                    inspected_source += inline_function_match.pre_match
                    source = inline_function_match.post_match
                    continue

                if re.search(self.function_declaration_parse_base_match + r'\s*\{', inline_function_match.post_match, flags=re.MULTILINE):
                    total_pairs_to_remove = self.count_number_of_pairs_of_braces_in_function(inline_function_match.post_match)

                    if total_pairs_to_remove == 0:
                        break

                    inline_function_stripped = inline_function_match.post_match

                    for _ in range(total_pairs_to_remove):
                        inline_function_stripped = re.sub(r'\s*' + square_bracket_pair_regex_format, ';', inline_function_stripped)

                    inspected_source += inline_function_match.pre_match
                    source = inline_function_stripped
                    continue

                inspected_source += inline_function_match.pre_match + inline_function_match.group(0)
                source = inline_function_match.post_match

        return source

    def import_source(self, source, parse_project, cpp=False):
        # let's clean up the encoding in case they've done anything weird with the characters we might find
        source = source.encode('ISO-8859-1').decode('utf-8', errors='replace')

        # void must be void for cmock _ExpectAndReturn calls to process properly, not some weird typedef which equates to void
        # to a certain extent, this action assumes we're chewing on pre-processed header files, otherwise we'll most likely just get stuff from @treat_as_void
        self.local_as_void = self.treat_as_void
        void_types = re.findall(r'typedef\s+(?:\(\s*)?void(?:\s*\))?\s+(\w+)\s*;', source)
        if void_types:
            self.local_as_void += list(set(void_types))

        # If user wants to mock inline functions,
        # remove the (user specific) inline keywords before removing anything else to avoid missing an inline function
        if self.treat_inlines == 'include':
            for user_format_string in self.inline_function_patterns:
                source = re.sub(user_format_string, '', source)

        # smush multiline macros into single line (checking for continuation character at end of line '\')
        source = re.sub(r'\s*\\\s*', ' ', source, flags=re.DOTALL)
        source = self.remove_comments_from_source(source)

        # remove assembler pragma sections
        source = re.sub(r'^\s*#\s*pragma\s+asm\s+.*?#\s*pragma\s+endasm', '', source, flags=re.DOTALL)

        # remove gcc's __attribute__ tags
        source = re.sub(r'__attribute(?:__)?\s*\(\(+.*\)\)+', '', source)

        # remove preprocessor statements and extern "C"
        source = re.sub(r'extern\s+"C"\s*\{', '', source)
        source = re.sub(r'^\s*#.*', '', source, flags=re.MULTILINE)

        # enums, unions, structs, and typedefs can all contain things (e.g. function pointers) that parse like function prototypes, so yank them
        # forward declared structs are removed before struct definitions so they don't mess up real thing later. we leave structs keywords in function prototypes
        source = re.sub(r'^[\w\s]*struct[^;{}()]+;', '', source, flags=re.MULTILINE)

         # remove struct, union, and enum definitions and typedefs with braces
        source = re.sub(r'^[\w\s]*(enum|union|struct|typedef)[\w\s]*\{[^}]+\}[\w\s*,]*;', '', source, flags=re.MULTILINE)

        # remove problem keywords
        source = re.sub(r'(\W)(?:register|auto|restrict)(\W)', r'\1\2', source)
        if not cpp:
            source = re.sub(r'(\W)(?:static)(\W)', r'\1\2', source)

        # remove default value statements from argument lists
        source = re.sub(r'\s*=\s*["\'a-zA-Z0-9_.]+\s*', '', source)

        # remove typedef statements
        source = re.sub(r'^(?:[\w\s]*\W)?typedef\W[^;]*', '', source, flags=re.MULTILINE)

        # add space between parenthese and alphanumeric
        source = re.sub(r'\)(\w)', r') \1', source)

        # remove known attributes slated to be stripped
        if self.c_strippables:
            source = re.sub(r'(^|\W+)(?:' + '|'.join(self.c_strippables) + r')(?=$|\W+)', r'\1', source)

        # scan standalone function pointers and remove them, because they can just be ignored
        source = re.sub(r'\w+\s*\(\s*\*\s*\w+\s*\)\s*\([^)]*\)\s*;', ';', source)

        def _replace_func_ptr(match):
            functype = f"cmock_{parse_project['module_name']}_func_ptr{len(parse_project['typedefs']) + 1}"
            parse_project['typedefs'].append(f"typedef {match.group(1).strip()}(*{functype})({match.group(4)});")
            return f"{functype} {match.group(2).strip()}({match.group(3)});"
        
        # scan for functions which return function pointers, because they are a pain
        source = re.sub(r'([\w\s*]+)\(*\(\s*\*([\w\s*]+)\s*\(([\w\s*,]*)\)\)\s*\(([\w\s*,]*)\)\)*', _replace_func_ptr, source)

        source = self.remove_nested_pairs_of_braces(source) if not cpp else source

        if self.treat_inlines == 'include':
            source = re.sub(r'\{ \}', ';', source)

        source = re.sub(r'\([^)]*\)\s*\{[^}]*\}', ';', source, flags=re.DOTALL)
        source = re.sub(r'^\s+', '', source, flags=re.MULTILINE)
        source = re.sub(r'\s+$', '', source, flags=re.MULTILINE)
        source = re.sub(r'\s*\(\s*', '(', source)
        source = re.sub(r'\s*\)\s*', ')', source)
        source = re.sub(r'\s+', ' ', source)

        if not cpp:
            # Use list(dict.fromkeys()) to remove duplicates while preserving order instead of list(set(..))
            src_lines = list(dict.fromkeys(re.split(r'\s*;\s*', source)))
        else:
            src_lines = re.split(r'\s*;\s*', source)
        src_lines = [line for line in src_lines if line.strip()]
        src_lines = [line for line in src_lines if not re.search(r'[\w\s*]+\(+\s*\*[*\s]*[\w\s]+(?:\[[\w\s]*\]\s*)+\)+\s*\((?:[\w\s*]*,?)*\s*\)', line)]

        if self.treat_externs != ':include':
            src_lines = [line for line in src_lines if not re.search(r'(?:^|\s+)(?:extern)\s+', line)]

        if self.treat_inlines != ':include':
            src_lines = [line for line in src_lines if not re.search(r'(?:^|\s+)(?:inline)\s+', line)]

        src_lines = [line for line in src_lines if line]

        return src_lines

    def parse_cpp_functions(self, source):
        funcs = []

        ns = []
        pub = False
        for line in source:
            for item in re.findall(r'(?:(?:\b(?:namespace|class)\s+(?:\S+)\s*)?{)|}', line):
                if item == '}':
                    ns.pop()
                else:
                    token = item.strip().replace(r'\s+', ' ')
                    ns.append(token)

                    if token.startswith('class'):
                        pub = False
                    if token.startswith('namespace'):
                        pub = True

            if re.search(r'public:', line):
                pub = True
            if re.search(r'private:', line) or re.search(r'protected:', line):
                pub = False

            if not pub or not re.search(r'\bstatic\b', line):
                continue

            line = re.sub(r'^.*static', '', line)
            if not re.search(self.declaration_parse_matcher, line):
                continue

            tmp = [item for item in ns if item != '{']

            cls = None
            if tmp and tmp[-1].startswith('class '):
                cls = tmp.pop().replace(r'class (\S+) {', r'\1')

            for item in tmp:
                item = item.replace(r'(?:namespace|class) (\S+) {', r'\1')

            funcs.append([line.strip().replace(r'\s+', ' '), tmp, cls])

        return funcs

    def parse_functions(self, filename, source):
        funcs = [line.strip().replace(r'\s+', ' ') for line in source if re.search(self.declaration_parse_matcher, line)]
        if not funcs:
            if self.when_no_prototypes == 'error':
                raise Exception(f"ERROR: No function prototypes found by CMock in {filename}")
            elif self.when_no_prototypes == 'warn' and self.verbosity >= 1:
                print(f"WARNING: No function prototypes found by CMock in {filename}")
        return funcs

    def parse_type_and_name(self, arg):
        arg = re.sub(r'(\w)\*', r'\1 *', arg)
        arg = re.sub(r'\*(\w)', r'* \1', arg)
        arg_array = arg.split()
        arg_info = self.divine_ptr_and_const(arg)
        arg_info['name'] = arg_array[-1]

        attributes = self.c_attr_noconst if '*' in arg else self.c_attributes
        attr_array = []
        type_array = []

        for word in arg_array[:-1]:
            if word in attributes:
                attr_array.append(word)
            elif word in self.c_calling_conventions:
                arg_info['c_calling_convention'] = word
            else:
                type_array.append(word)

        if arg_info['const_ptr?']:
            attr_array.append('const')
            type_array.remove('const')

        arg_info['modifier'] = ' '.join(attr_array)
        arg_info['type'] = re.sub(r'\s+\*', '*', ' '.join(type_array))
        return arg_info

    def parse_args(self, arg_list):
        args = []
        for arg in arg_list.split(','):
            arg = arg.strip()
            if re.search(r'^\s*((\.\.\.)|(void))\s*$', arg):
                return args

            arg_info = self.parse_type_and_name(arg)
            arg_info.pop('modifier', None)
            arg_info.pop('c_calling_convention', None)

            if self.treat_as_array.get(arg_info['type']) and not arg_info['ptr?']:
                arg_info['type'] = f"{self.treat_as_array[arg_info['type']]}*"
                if arg_info['const?']:
                    arg_info['type'] = f"const {arg_info['type']}"
                arg_info['ptr?'] = True

            args.append(arg_info)

        for index, val in enumerate(args):
            next_index = index + 1
            if len(args) > next_index and val['ptr?'] and re.search(self.array_size_name, args[next_index]['name']) and args[next_index]['type'] in self.array_size_type:
                val['array_data?'] = True
                args[next_index]['array_size?'] = True

        return args

    def divine_ptr(self, arg):
        if '*' not in arg:
            return False
        if re.search(r'(^|\s)(const\s+)?char(\s+const)?\s*\*(?!.*\*)', arg):
            return False
        return True

    def divine_const(self, arg):
        if '*' in arg:
            return bool(re.search(r'(^|\s|\*)const(\s(\w|\s)*)?\*(?!.*\*)', arg))
        return bool(re.search(r'(^|\s)const(\s|$)', arg))

    def divine_ptr_and_const(self, arg):
        divination = {}
        divination['ptr?'] = self.divine_ptr(arg)
        divination['const?'] = self.divine_const(arg)
        divination['const_ptr?'] = bool(re.search(r'\*(?!.*\*)\s*const(\s|$)', arg))
        return divination

    def clean_args(self, arg_list, parse_project):
        if arg_list.strip() in self.local_as_void or not arg_list:
            return 'void'
        c = 0
        arg_list = re.sub(r'(\w+)(?:\s*\[[^\[\]]*\])+', r'*\1', arg_list)
        arg_list = re.sub(r'\s+\*', '*', arg_list)
        arg_list = re.sub(r'\*(\w)', r'* \1', arg_list)

        def _replace_func_ptr(match):
            functype = f"cmock_{parse_project['module_name']}_func_ptr{len(parse_project['typedefs']) + 1}"
            parse_project['typedefs'].append(f"typedef {match.group(1).strip()}(*{functype})({match.group(4)});")
            return f"{functype} {match.group(2).strip()}({match.group(3)});"

        arg_list = re.sub(r'([\w\s*]+)\(+([\w\s]*)\*[*\s]*([\w\s]*)\s*\)+\s*\(((?:[\w\s*]*,?)*)\s*\)*', _replace_func_ptr, arg_list)

        def _replace_func_ptr_shorthand(match):
            functype = f"cmock_{parse_project['module_name']}_func_ptr{len(parse_project['typedefs']) + 1}"
            parse_project['typedefs'].append(f"typedef {match.group(1).strip()}(*{functype})({match.group(3)});")
            return f"{functype} {match.group(2).strip()}"
        
        arg_list = re.sub(r'([\w\s*]+)\s+(\w+)\s*\(((?:[\w\s*]*,?)*)\s*\)*', _replace_func_ptr_shorthand, arg_list)

        arg_list = self._create_dummy_names(arg_list)
        return arg_list
    
    def _create_dummy_names(self, arg_list):
        cleaned_args = []
        keywords_to_remove = ['struct', 'union', 'enum', 'const', 'const*']
        for c, arg in enumerate(re.split(r'\s*,\s*', arg_list)):
            parts = [part for part in arg.split() if part not in keywords_to_remove]
            if len(parts) < 2 or parts[-1][-1] == '*' or parts[-1] in self.standards:
                cleaned_args.append(f"{arg} cmock_arg{c + 1}")
            else:
                cleaned_args.append(arg)
        return ', '.join(cleaned_args)

    def parse_declaration(self, parse_project, declaration, namespace=None, classname=None):
        if namespace is None:
            namespace = []
        decl = {}
        decl['namespace'] = namespace
        decl['class'] = classname

        regex_match = self.declaration_parse_matcher.match(declaration)
        if regex_match is None:
            raise Exception(f"Failed parsing function declaration: '{declaration}'")

        # grab argument list
        args = regex_match.group(2).strip()

        # process function attributes, return type, and name
        parsed = self.parse_type_and_name(regex_match.group(1))

        # Record original name without scope prefix
        decl['unscoped_name'] = parsed['name']

        # Prefix name with namespace scope (if any) and then class
        decl['name'] = '_'.join(namespace)
        if classname:
            if decl['name']:
                decl['name'] += '_'
            decl['name'] += classname
        # Add original name to complete fully scoped name
        if decl['name']:
            decl['name'] += '_'
        decl['name'] += decl['unscoped_name']

        decl['modifier'] = parsed['modifier']
        if 'c_calling_convention' in parsed:
            decl['c_calling_convention'] = parsed['c_calling_convention']

        rettype = parsed['type']
        if rettype.strip() in self.local_as_void:
            rettype = 'void'
        decl['return'] = {
            'type': rettype,
            'name': 'cmock_to_return',
            'str': f"{rettype} cmock_to_return",
            'void?': (rettype == 'void'),
            'ptr?': parsed.get('ptr?', False),
            'const?': parsed.get('const?', False),
            'const_ptr?': parsed.get('const_ptr?', False)
        }

        # remove default argument statements from mock definitions
        args = re.sub(r'=\s*[a-zA-Z0-9_.]+\s*', ' ', args)

        # check for var args
        if '...' in args:
            decl['var_arg'] = re.search(r'[\w\s]*\.\.\.', args).group().strip()
            if ', ...' in args:
                args = re.sub(r',[\w\s]*\.\.\.', '', args)
            else:
                args = 'void'
        else:
            decl['var_arg'] = None

        args = self.clean_args(args, parse_project)
        decl['args_string'] = args
        decl['args'] = self.parse_args(args)
        decl['args_call'] = ', '.join([a['name'] for a in decl['args']])
        decl['contains_ptr?'] = any(arg['ptr?'] for arg in decl['args'])

        if not decl['return']['type'] or not decl['name'] or decl['args'] == None:
            raise Exception(
                f"Failed Parsing Declaration Prototype!\n"
                f"  declaration: '{declaration}'\n"
                f"  modifier: '{decl['modifier']}'\n"
                f"  return: {self.prototype_inspect_hash(decl['return'])}\n"
                f"  function: '{decl['name']}'\n"
                f"  args: {self.prototype_inspect_array_of_hashes(decl['args'])}\n"
            )

        return decl

    def prototype_inspect_hash(self, hash):
        pairs = []
        for name, value in hash.items():
            if isinstance(value, str):
                pairs.append(f"{name} => \\{value}\\")
            else:
                pairs.append(f"{name} => {value}")
        
        return f"{{{', '.join(pairs)}}}"

    def prototype_inspect_array_of_hashes(self, array):
        hashes = [self.prototype_inspect_hash(hash) for hash in array]
        if len(array) == 0:
            return '[]'
        elif len(array) == 1:
            return f"[{hashes[0]}]"
        else:
            hashesString = '\n    '.join(hashes)
            return f"[\n    {hashesString}\n  ]\n"
