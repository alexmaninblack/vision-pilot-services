/* SPDX-FileCopyrightText: 2026 maninblack
 * SPDX-License-Identifier: Apache-2.0 */
#include <stdio.h>
#include <sys/prctl.h>
#include <unistd.h>

int main(int argc,char **argv) {
    (void)argv;
    if (argc!=1 || getuid()==0 || getgid()==0 || getuid()!=geteuid() || getgid()!=getegid()
        || prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0)) {
        fputs("VISION_NATIVE_LAUNCH_REJECTED\n",stderr);return 1;
    }
    char *args[]={"/usr/bin/python3.12","-I","-B","/app/entry.py",NULL};
    char *environment[]={"PATH=/usr/bin","LANG=C.UTF-8","OPENBLAS_NUM_THREADS=1","OMP_NUM_THREADS=1",NULL};
    execve(args[0],args,environment);
    fputs("VISION_NATIVE_EXEC_REJECTED\n",stderr);return 1;
}
