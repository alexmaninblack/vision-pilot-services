# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
import io
from pathlib import Path
import runpy
import tarfile
import unittest
from unittest.mock import patch

MODULE=runpy.run_path(str(Path(__file__).resolve().parents[1]/'tools/aos_package.py'))


def archive(rows):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as output:
        for name,data,kind in rows:
            row=tarfile.TarInfo(name);row.type=kind;row.size=len(data) if kind==tarfile.REGTYPE else 0
            if kind==tarfile.SYMTYPE:row.linkname='outside'
            output.addfile(row,io.BytesIO(data) if row.isfile() else None)
    return stream.getvalue()


class AosProfilesTests(unittest.TestCase):
    def test_license_case_aliases_keep_both_bytes_and_ship_original_path_map(self):
        original={'app/notices/bzip2/LICENSE.txt':(b'one',0o444),'app/notices/bzip2/License.txt':(b'two',0o444),'app/module.py':(b'code',0o444)}
        payload,mapping=MODULE['portable_notices'](original)
        self.assertEqual(payload['app/module.py'],original['app/module.py']);self.assertEqual(len(mapping),2)
        self.assertEqual({payload[row['packaged']][0] for row in mapping},{b'one',b'two'})
        self.assertIn('app/notices/packaging-paths.json',payload)
        for bad in ({'app/M.py':(b'a',0o444),'app/m.py':(b'b',0o444)},
                {'app/notices/Upper/a':(b'a',0o444),'app/notices/upper/b':(b'b',0o444)}):
            with self.assertRaises(ValueError):MODULE['portable_notices'](bad)

    def test_official_signer_dot_root_is_closed_and_duplicate_aliases_still_fail(self):
        raw=archive([('.',b'',tarfile.DIRTYPE),('./config.yaml',b'{}',tarfile.REGTYPE)])
        self.assertEqual(MODULE['files'](raw,'assessment',signer_archive=True)['config.yaml'][0],b'{}')
        with self.assertRaises(ValueError):MODULE['files'](raw,'assessment')
        for rows in ([('./a',b'x',tarfile.REGTYPE),('a',b'y',tarfile.REGTYPE)],
                [('././a',b'x',tarfile.REGTYPE)],[('.',b'x',tarfile.REGTYPE)]):
            with self.assertRaises(ValueError):MODULE['files'](archive(rows),'assessment',signer_archive=True)

    def test_the_larger_profile_is_only_perception(self):
        profiles=MODULE['PROFILES'];self.assertEqual(profiles['perception']['expanded'],512*1024**2)
        self.assertEqual(profiles['assessment']['expanded'],256*1024**2)
        raw=archive([('file',b'a'*100,tarfile.REGTYPE)])
        self.assertEqual(MODULE['files'](raw,'assessment')['file'][0],b'a'*100)
        with patch.dict(profiles['assessment'],expanded=50):
            with self.assertRaisesRegex(ValueError,'EXPANSION_LIMIT'):MODULE['files'](raw,'assessment')
        with self.assertRaisesRegex(ValueError,'PROFILE_INVALID'):MODULE['files'](raw,'brake')

    def test_links_duplicates_escape_and_path_aliases_rejected(self):
        for rows in ([('../escape',b'',tarfile.REGTYPE)],[('/absolute',b'',tarfile.REGTYPE)],[('a//b',b'',tarfile.REGTYPE)],
                [('link',b'',tarfile.SYMTYPE)],[('same',b'a',tarfile.REGTYPE),('same',b'b',tarfile.REGTYPE)],
                [('a',b'a',tarfile.REGTYPE),('a/b',b'b',tarfile.REGTYPE)]):
            with self.assertRaises(ValueError):MODULE['files'](archive(rows),'perception')

    def test_fixed_roles_and_no_application_network_or_arbitrary_entrypoint(self):
        quotas=dict(cpuLimit=1,ramLimit=1,storageLimit=1,stateLimit=1,tmpLimit=1,noFileLimit=1024,pidsLimit=64)
        for role,resources in (('perception',['vision-camera-read','vision-perception-publish']),
                ('assessment',['vision-perception-read','vision-context-read','vision-assessment-publish'])):
            config=MODULE['configuration'](role,quotas)['items'][0]['configuration']
            self.assertEqual(config['resources'],[dict(name=name) for name in resources]);self.assertEqual(config['allowedConnections'],[])
            self.assertEqual(config['cmd'],'/usr/bin/vision-'+role);self.assertNotIn('env',config);self.assertNotIn('permissions',config)
        quotas['cpuLimit']=True
        with self.assertRaises(ValueError):MODULE['configuration']('perception',quotas)


if __name__=='__main__':unittest.main()
