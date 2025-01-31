# =========================================================================
#   pyCMock - Automatic Mock Generation for C
#   
#   Copyright (c) 2025 Christian Renzel
#   SPDX-License-Identifier: MIT
# =========================================================================

import os
import shutil
import filecmp

class CMockFileWriter:
    def __init__(self, config):
        self.config = config

    def create_subdir(self, subdir=None):
        """
        Create the necessary subdirectories for mock generation.
        """
        mock_path = self.config.options['mock_path']
        os.makedirs(mock_path, exist_ok=True)
        if subdir:
            subdir_path = os.path.join(mock_path, subdir)
            os.makedirs(subdir_path, exist_ok=True)

    def create_file(self, filename, callback, subdir, *args, **kwargs):
        """
        Create a new file, writing its contents using a provided block (callback).
        Uses a temp file to avoid unnecessary writes.
        """
        if not callable(callback):
            raise ValueError("A callable block must be provided to generate file contents.")

        mock_path = self.config.options['mock_path']
        subdir_path = os.path.join(mock_path, subdir) if subdir else mock_path
        os.makedirs(subdir_path, exist_ok=True)

        final_file = os.path.join(subdir_path, filename)
        temp_file = f"{final_file}.new"

        with open(temp_file, 'w') as file:
            callback(file, *args, **kwargs)

        # Avoid unnecessary file updates
        if os.path.exists(final_file) and filecmp.cmp(temp_file, final_file, shallow=False):
            os.remove(temp_file)  # No change, discard temp file
        else:
            shutil.move(temp_file, final_file)  # Replace only if changed

    def append_file(self, filename, callback, subdir, *args, **kwargs):
        """
        Append data to an existing file, writing the content using a provided block (callback).
        """
        if not callable(callback):
            raise ValueError("A callable block must be provided to generate file contents.")

        skeleton_path = self.config['skeleton_path']
        subdir_path = os.path.join(skeleton_path, subdir) if subdir else skeleton_path
        os.makedirs(subdir_path, exist_ok=True)

        full_file = os.path.join(subdir_path, filename)

        with open(full_file, 'a') as file:
            callback(file, *args, **kwargs)

    def _update_file(self, dest, src):
        """
        Replace the destination file with the source file.
        """
        try:
            os.remove(dest)
        except FileNotFoundError:
            pass
        shutil.move(src, dest)
