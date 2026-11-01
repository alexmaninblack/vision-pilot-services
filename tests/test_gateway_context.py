# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
import unittest
from vision_common import protocol as p
import fixtures as f


class ContextBoundaryTests(unittest.TestCase):
    def test_gateway_cannot_choose_native_epoch(self):
        local=f.context();wire=dict(local,kind='gateway-context',binding={k:v for k,v in local['binding'].items() if k!='componentEpoch'})
        self.assertEqual(p.gateway_context(wire,f.uid(1)),local)
        wire['binding']['componentEpoch']=f.uid(99)
        with self.assertRaises(p.Invalid):p.gateway_context(wire,f.uid(1))

    def test_solver_failure_guard_is_pinned(self):
        from pathlib import Path
        import hashlib,json
        root=Path(__file__).resolve().parents[1]
        pin=json.loads((root/'dependencies/upstream.json').read_bytes())
        row=next(r for r in pin['importedFiles'] if r['path'].endswith('/lateral_planning.cpp'))
        raw=(root/row['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
        self.assertIn(b'if (solution.status != CppAD::ipopt::solve_result<Dvector>::success) return {};',raw)
        self.assertIn(b'Numeric max_cpu_time 0.015',raw)


if __name__=='__main__':unittest.main()
