#!/usr/bin/env python3
# =========================================================================
#   pyCMock - Automatic Mock Generation for C
#   
#   Copyright (c) 2025 Christian Renzel
#   SPDX-License-Identifier: MIT
# =========================================================================

import re

class TypeSanitizer:
    def sanitize_c_identifier(self, unsanitized):
        # convert filename to valid C identifier by replacing invalid chars with '_'
        return re.sub(r'[-\/\\.,\s]', '_', unsanitized)
