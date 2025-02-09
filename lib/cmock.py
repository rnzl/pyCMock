#!/usr/bin/env python3
# =========================================================================
#   pyCMock - Automatic Mock Generation for C
#   
#   Copyright (c) 2025 Christian Renzel
#   SPDX-License-Identifier: MIT
# =========================================================================

import os
import sys
import yaml
from cmock_config import CMockConfig
from cmock_unityhelper_parser import CMockUnityHelperParser
from cmock_file_writer import CMockFileWriter
from cmock_generator_utils import CMockGeneratorUtils
from cmock_plugin_manager import CMockPluginManager
from cmock_header_parser import CMockHeaderParser
from cmock_generator import CMockGenerator

class CMock:
    def __init__(self, options=None):
        cm_config = CMockConfig(options)
        cm_unityhelper = CMockUnityHelperParser(cm_config)
        cm_writer = CMockFileWriter(cm_config)
        cm_gen_utils = CMockGeneratorUtils(cm_config, helpers={'unity_helper': cm_unityhelper})
        cm_gen_plugins = CMockPluginManager(cm_config, cm_gen_utils)
        self.cm_parser = CMockHeaderParser(cm_config)
        self.cm_generator = CMockGenerator(cm_config, cm_writer, cm_gen_utils, cm_gen_plugins)
        self.silent = cm_config.options['verbosity'] < 2

    def setup_mocks(self, files, folder=None):
        for src in files if isinstance(files, list) else [files]:
            self.generate_mock(src, folder)

    def setup_skeletons(self, files):
        for src in files if isinstance(files, list) else [files]:
            self.generate_skeleton(src)

    def generate_mock(self, src, folder):
        name, ext = os.path.splitext(os.path.basename(src))
        if not self.silent:
            print(f"Creating mock for {name}...")
        with open(src, 'r') as f:
            content = f.read()
        self.cm_generator.create_mock(name, self.cm_parser.parse(name, content), ext, folder)

    def generate_skeleton(self, src):
        name, _ = os.path.splitext(os.path.basename(src))
        if not self.silent:
            print(f"Creating skeleton for {name}...")
        with open(src, 'r') as f:
            content = f.read()
        self.cm_generator.create_skeleton(name, self.cm_parser.parse(name, content))


def option_maker(options, key, val):
    if options is None:
        options = {}
    if val.startswith(':'):
        options[key] = val[1:]
    elif ';' in val:
        options[key] = val.split(';')
    elif val.lower() == 'true':
        options[key] = True
    elif val.lower() == 'false':
        options[key] = False
    elif val.isdigit():
        options[key] = int(val)
    else:
        options[key] = val
    return options


if __name__ == "__main__":
    usage = f"usage: python {sys.argv[0]} (-oOptionsFile) File(s)ToMock"

    if len(sys.argv) < 2:
        print(usage)
        sys.exit(1)

    options = {}
    filelist = []
    opt_flag = False

    for arg in sys.argv[1:]:
        if arg.startswith('-o'):
            if len(arg) > 2:
                config = CMockConfig()
                options.update(config.load_config_file_from_yaml(arg[2:]))
            else:
                opt_flag = True
        elif arg == '--skeleton':
            options['skeleton'] = True
        elif arg == '--version':
            from cmock_version import CMOCK_VERSION
            print(CMOCK_VERSION)
            sys.exit(0)
        elif arg.startswith('--strippables='):
            options = option_maker(options, 'strippables', arg.split('=', 1)[1])
        elif '=' in arg:
            key, val = arg.split('=', 1)
            options = option_maker(options, key.lstrip('--'), val)
        else:
            if opt_flag:
                config = CMockConfig()
                options.update(config.load_config_file_from_yaml(arg))
                opt_flag = False
            else:
                filelist.append(arg)

    cmock = CMock(options)
    if options.get('skeleton'):
        cmock.setup_skeletons(filelist)
    else:
        cmock.setup_mocks(filelist)
