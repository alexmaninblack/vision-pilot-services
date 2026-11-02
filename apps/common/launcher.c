/* SPDX-FileCopyrightText: 2026 maninblack
 * SPDX-License-Identifier: Apache-2.0 */
#define _GNU_SOURCE
#include <errno.h>
#include <limits.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <stdio.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/syscall.h>
#include <unistd.h>

_Static_assert(__NR_socket==198 && __NR_socketpair==199 && AUDIT_ARCH_AARCH64==0xc00000b7,
    "This fixed native entry is Linux ARM64 only");
_Static_assert(AF_UNIX==1 && EPERM==1,"Unexpected Linux socket/errno ABI");

static int unix_only(void) {
    /* Same 21 instructions proven transiently in the actual Aos identities.
     * Wrong ABI kills; socket/socketpair permit AF_UNIX only. Block io_uring
     * so its socket operation cannot bypass the ordinary socket syscall gate.
     * No Core/VM firewall/UID authority or new resource is introduced. */
    static const struct sock_filter filter[]={
        {0x20,0,0,4}, {0x15,1,0,0xc00000b7}, {0x06,0,0,0x80000000},
        {0x20,0,0,0}, {0x15,0,3,198}, {0x20,0,0,16}, {0x15,1,0,1}, {0x06,0,0,0x50001},
        {0x20,0,0,0}, {0x15,0,3,199}, {0x20,0,0,16}, {0x15,1,0,1}, {0x06,0,0,0x50001},
        {0x20,0,0,0}, {0x15,0,1,425}, {0x06,0,0,0x50001}, {0x15,0,1,426}, {0x06,0,0,0x50001},
        {0x15,0,1,427}, {0x06,0,0,0x50001}, {0x06,0,0,0x7fff0000}
    };
    struct sock_fprog program={.len=sizeof(filter)/sizeof(filter[0]),.filter=(struct sock_filter *)filter};
    return prctl(PR_SET_SECCOMP,SECCOMP_MODE_FILTER,&program,0,0);
}

int main(int argc,char **argv) {
    (void)argv;
    if (argc!=1 || getuid()==0 || getgid()==0 || getuid()!=geteuid() || getgid()!=getegid()
        || prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0) || close_range(3,UINT_MAX,0) || unix_only()) {
        fputs("VISION_NATIVE_LAUNCH_REJECTED\n",stderr);return 1;
    }
    char *args[]={"/usr/bin/python3.12","-I","-B","/app/entry.py",NULL};
    char *environment[]={"PATH=/usr/bin","LANG=C.UTF-8","OPENBLAS_NUM_THREADS=1","OMP_NUM_THREADS=1",NULL};
    execve(args[0],args,environment);
    fputs("VISION_NATIVE_EXEC_REJECTED\n",stderr);return 1;
}
