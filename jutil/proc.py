# SPDX-FileCopyRightText: Copyright (c) 2022-present Jeffrey LeBlanc
# SPDX-License-Indentifier: MIT

import subprocess
import shlex

class ProcError(Exception):
    pass

def proc(cmd, cwd=None):
    if isinstance(cmd,str):
        cmd = shlex.split(cmd)
    r = subprocess.run(cmd,capture_output=True,cwd=cwd)
    return (
        r.returncode,
        r.stdout.decode("utf-8"),
        r.stderr.decode("utf-8")
    )

def proc0(cmd, cwd=None, quiet=False):
    if isinstance(cmd,str):
        cmd = shlex.split(cmd)
    r = subprocess.run(cmd,capture_output=True,cwd=cwd)
    if r.returncode != 0:
        if not quiet:
            print("---------------------------------------------")
            print(f"ERROR RUNNING:\n{cmd}\n")
            print(f"ERROR stdout:\n{r.stdout.decode('utf-8')}\n")
            print(f"ERROR RUNNING:\n{r.stderr.decode('utf-8')}\n")
            print("---------------------------------------------")
        err = ProcError(f"proc0: Above returned code {r.returncode}")
        err.cmd_code = r.returncode
        err.cmd_stdout = r.stdout.decode("utf-8")
        err.cmd_stderr = r.stderr.decode("utf-8")
        raise err
    return (
        r.returncode,
        r.stdout.decode("utf-8"),
        r.stderr.decode("utf-8")
    )


def command_pretty_format(cmd_list, flag_start="-"):
    """
    Takes a command as a shlex list and formats in on multiple lines with \
    """
    s = ""
    last_was_flag = False
    curr_is_flag = False
    LST = []

    # Form line pairs
    for e in cmd_list:
        e = str(e)
        curr_is_flag = e.startswith(flag_start)

        if curr_is_flag:
            LST.append([e])
        else:
            if last_was_flag:
                LST[-1].append(e)
            else:
                LST.append([e])

        last_was_flag = curr_is_flag

    # Assemble the string
    for i,parts in enumerate(LST):
        s += ( " "*4 if i!=0 else "" ) + " ".join(parts)
        if i != len(LST)-1:
            s += " \\\n"

    return s
