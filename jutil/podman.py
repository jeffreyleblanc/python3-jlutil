# SPDX-FileCopyRightText: Copyright (c) 2022-present Jeffrey LeBlanc
# SPDX-License-Indentifier: MIT

from dataclasses import dataclass
from .proc import proc
import json

@dataclass
class ContainerReport:
    name: str
    on: bool
    obj: dict

def podman_ps(*, prefix=None, _all=True, raw=False):
    c,o,e = proc("podman ps --all --format=json")
    raw_obj = json.loads(o)
    if raw:
        return raw_obj
    else:
        containers = []
        for c_dict in raw_obj:
            name = c_dict["Names"][0]
            if prefix is not None and not name.startswith(prefix):
                continue
            on = not c_dict["Exited"]
            c = ContainerReport(name=name,on=on,obj=c_dict)
            containers.append(c)
        containers.sort(key=lambda e:e.name)
        return containers

