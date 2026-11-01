# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import runpy
import unittest


class ClosureOwnershipTests(unittest.TestCase):
    def test_header_notices_require_regular_files_not_symlinks(self):
        import tempfile
        function=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tools/build_closure.py'))['regular_header_notice']
        with tempfile.TemporaryDirectory() as temporary:
            notice=Path(temporary)/'notice';notice.write_text('Synthetic unit notice')
            self.assertEqual(function(notice),notice)
            linked=notice.with_name('linked');linked.symlink_to(notice)
            for path in (linked,notice.with_name('missing'),notice.parent):
                with self.assertRaisesRegex(ValueError,'HEADER_BUILD_NOTICE_ABSENT'):function(path)

    def test_yocto_package_qualified_file_and_license_fields_are_not_discarded(self):
        function=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tools/build_closure.py'))['package_fields']
        fields=function('PN: libgcc\nPV: 13.4.0\nLICENSE: wrong-default\nLICENSE:libgcc: GPL-3.0-with-GCC-exception\nFILES_INFO:libgcc: {"/usr/lib/libgcc_s.so.1":133016}\n','libgcc')
        self.assertEqual(fields['LICENSE'],'GPL-3.0-with-GCC-exception');self.assertIn('/usr/lib/libgcc_s.so.1',fields['FILES_INFO'])

    def test_package_aliases_require_the_same_real_file_and_one_owner(self):
        source=Path(__file__).resolve();owner=runpy.run_path(str(source.parents[1]/'tools/build_closure.py'))['package_owner']
        def query(args,**kwargs):
            self.assertEqual(args,['dpkg-query','-S','*/'+source.name]);return 'example:arm64: '+str(source)+'\nexample:arm64: '+str(source)+'\n'
        self.assertEqual(owner(source,query),'example:arm64')
        with self.assertRaisesRegex(ValueError,'PACKAGE_AMBIGUOUS'):
            owner(source,lambda *args,**kwargs:'first: '+str(source)+'\nsecond: '+str(source)+'\n')
        with self.assertRaisesRegex(ValueError,'PACKAGE_AMBIGUOUS'):
            owner(source,lambda *args,**kwargs:'unknown: /absent/'+source.name+'\n')


if __name__=='__main__':unittest.main()
