# SPDX-FileCopyRightText: Copyright (c) 2022-present Jeffrey LeBlanc
# SPDX-License-Indentifier: MIT

from pathlib import Path
import shutil
from .proc import proc0

def empty_directory(directory: Path) -> None:
    # Note, in research it seems generally faster to delete the root directory and recreate
    # versus walking it recursively and deleting all the directories/files individually
    if directory.exists():
        if directory.is_dir():
            shutil.rmtree(directory)
        else:
            raise Exception(f"NOT A DIRECTORY: {directory}")
    directory.mkdir()


def filetree(directory: Path, *, clean=True) -> str:
    c,o,e = proc0(["tree","--charset=ascii","--noreport","-nF",directory])
    filetree = o.strip()
    if clean:
        indent = " "*4
        for e in ("`-- ","|-- ","|   "):
            filetree = filetree.replace(e,indent)
    return filetree

