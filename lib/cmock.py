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
import argparse
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
    if key not in options:
        options[key] = []
    options[key].append(val)
    return options


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CMock - Automatic Mock Generation for C")
    parser.add_argument('-o', '--options', help="Options file", required=False)
    parser.add_argument('--skeleton', action='store_true', help="Generate skeletons")
    parser.add_argument('--version', action='store_true', help="Show version")
    parser.add_argument('--strippables', help="Strippables", required=False)
    parser.add_argument('files', nargs='*', help="Files to mock")

    args = parser.parse_args()

    print(args)

    if args.version:
        from cmock_version import CMOCK_VERSION
        print(CMOCK_VERSION)
        sys.exit(0)

    options = {}
    if args.options:
        config = CMockConfig()
        options.update(config.load_config_file_from_yaml(args.options))

    if args.skeleton:
        options['skeleton'] = True

    if args.strippables:
        options = option_maker(options, 'strippables', args.strippables)

    filelist = args.files

    cmock = CMock(options)
    if options.get('skeleton'):
        cmock.setup_skeletons(filelist)
    else:
        cmock.setup_mocks(filelist)
