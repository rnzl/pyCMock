# =========================================================================
#   pyCMock - Automatic Mock Generation for C
#   
#   Copyright (c) 2025 Christian Renzel
#   SPDX-License-Identifier: MIT
# =========================================================================

import os
import shutil


class CMockFileWriter:
    def __init__(self, config):
        self.config = config

    def create_subdir(self, subdir=None):
        """
        Create the necessary subdirectories for mock generation.
        """
        mock_path = self.config['mock_path']
        os.makedirs(mock_path, exist_ok=True)
        if subdir:
            subdir_path = os.path.join(mock_path, subdir)
            os.makedirs(subdir_path, exist_ok=True)

    def create_file(self, filename, subdir=None):
        """
        Create a new file, writing its contents using a provided block (callback).
        """
        if not callable(filename):
            raise ValueError("A callable block must be provided to generate file contents.")

        mock_path = self.config['mock_path']
        subdir_path = os.path.join(mock_path, subdir) if subdir else mock_path
        os.makedirs(subdir_path, exist_ok=True)

        temp_file = os.path.join(subdir_path, f"{filename}.new")
        final_file = os.path.join(subdir_path, filename)

        with open(temp_file, 'w') as file:
            filename(file, filename)

        self._update_file(final_file, temp_file)

    def append_file(self, filename, subdir=None):
        """
        Append data to an existing file, writing the content using a provided block (callback).
        """
        if not callable(filename):
            raise ValueError("A callable block must be provided to generate file contents.")

        skeleton_path = self.config['skeleton_path']
        subdir_path = os.path.join(skeleton_path, subdir) if subdir else skeleton_path
        os.makedirs(subdir_path, exist_ok=True)

        full_file = os.path.join(subdir_path, filename)

        with open(full_file, 'a') as file:
            filename(file, filename)

    def _update_file(self, dest, src):
        """
        Replace the destination file with the source file.
        """
        try:
            os.remove(dest)
        except FileNotFoundError:
            pass
        shutil.move(src, dest)
