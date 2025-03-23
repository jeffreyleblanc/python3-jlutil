# SPDX-FileCopyRightText: Copyright (c) 2023-present Jeffrey LeBlanc
# SPDX-License-Indentifier: MIT

import subprocess
import shlex

def proc(cmd):
    if isinstance(cmd,str):
        cmd = shlex.split(cmd)
    r = subprocess.run(cmd,capture_output=True)
    return (
        r.returncode,
        r.stdout.decode('utf-8'),
        r.stderr.decode('utf-8')
    )