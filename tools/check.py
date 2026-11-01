#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""One isolated source gate; never starts real models, VM, Cloud or simulator."""
import ast
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
for relative in ('common','apps/perception','apps/assessment'):
    sys.path.insert(0,str(ROOT/relative))


def main():
    for parent in ('common','apps','tools','tests'):
        for path in (ROOT/parent).rglob('*.py'):
            source=path.read_text();ast.parse(source)
            assert 'SPDX-FileCopyrightText: 2026 maninblack' in source
            assert 'SPDX-License-Identifier: Apache-2.0' in source
    for path in ROOT.rglob('*.json'):
        if not any(p in ('.git','.tmp','.local','build') for p in path.parts):json.loads(path.read_bytes())
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_*.py')
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() and result.testsRun>0 else 1


if __name__=='__main__':raise SystemExit(main())
