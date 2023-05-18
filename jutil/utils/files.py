# SPDX-FileCopyRightText: Copyright (c) 2023-present Jeffrey LeBlanc
# SPDX-License-Indentifier: MIT

def merge_files(sources=[], dest=None):
    # I don't love this solution, but ok here
    with open(dest,'w') as out:
        for fn in sources:
            with open(fn) as src:
                out.write(src.read())
