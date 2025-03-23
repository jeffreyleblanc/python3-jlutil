# SPDX-FileCopyRightText: Copyright (c) 2023-present Jeffrey LeBlanc
# SPDX-License-Indentifier: MIT

from .proc import proc

def ensure_ssh_keys_available():
    c,o,e = proc("ssh-add -L")
    print("c:",c)
    print("o:",o)
    print("e:",e)
    if c == 0:
        return True
    else:
        return False
