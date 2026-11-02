# SPDX-FileCopyrightText: 2026 maninblack
# SPDX-License-Identifier: Apache-2.0
"""Pure cBPF policy units. Never starts a native process, socket or VM."""
from pathlib import Path
import re
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'apps/common/launcher.c'


def program():
    text=SOURCE.read_text().split('static const struct sock_filter filter[]={',1)[1].split('};',1)[0]
    rows=re.findall(r'\{(0x[0-9a-f]+|\d+),(\d+),(\d+),(0x[0-9a-f]+|\d+)\}',text)
    return [tuple(int(v,0) for v in row) for row in rows]


def evaluate(number,domain=0,architecture=0xc00000b7):
    rows=program();pc=0;accumulator=0;data={0:number,4:architecture,16:domain}
    for _ in range(100):
        code,jt,jf,k=rows[pc]
        if code==0x20:accumulator=data[k];pc+=1
        elif code==0x15:pc+=1+(jt if accumulator==k else jf)
        elif code==0x06:return k
        else:raise AssertionError('Unexpected filter instruction')
    raise AssertionError('Unbounded filter')


class LauncherTests(unittest.TestCase):
    def test_only_unix_sockets_and_socketpairs(self):
        self.assertEqual(len(program()),21)
        for number in (198,199):
            self.assertEqual(evaluate(number,1),0x7fff0000)
            for domain in (0,2,10,16,17,40,0xffffffff):self.assertEqual(evaluate(number,domain),0x50001)

    def test_io_uring_cannot_create_an_internet_socket(self):
        for number in (425,426,427):self.assertEqual(evaluate(number),0x50001)

    def test_other_abi_kills_and_normal_file_model_thread_calls_remain(self):
        self.assertEqual(evaluate(198,1,0xc000003e),0x80000000)
        for number in (56,57,63,64,98,172,220,221,222):self.assertEqual(evaluate(number),0x7fff0000)

    def test_fixed_entry_closes_inherited_handles_and_fails_closed(self):
        source=SOURCE.read_text()
        self.assertIn('argc!=1',source);self.assertIn('getuid()==0',source)
        self.assertIn('close_range(3,UINT_MAX,0) || unix_only()',source)
        self.assertLess(source.index('|| unix_only()'),source.index('execve(args[0],args,environment)'))
        self.assertNotIn('getenv(',source)


if __name__=='__main__':unittest.main()
