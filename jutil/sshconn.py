# SPDX-FileCopyRightText: Copyright (c) 2022-present Jeffrey LeBlanc
# SPDX-License-Indentifier: MIT

import paramiko

"""
https://docs.paramiko.org/en/stable/api/client.html
"""

class SSHConn:

    def __init__(self, address=None, username=None):
        self.address = address
        self.username = username
        self._client = None

    def connect(self):
        """
        This method needs review, options, and error handling
        """
        self._client = paramiko.client.SSHClient()
        # => seems to not be picking up clients manually connected to?
        # demo.photon.ac for example
        # Thus doing the auto add policy for now
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(self.address,username=self.username,allow_agent=True)

    def disconnect(self):
        self._client.close()

    def exec(self, command_string, as_dict=False):
        _stdin,_stdout,_stderr = self._client.exec_command(command_string)
        return_code = _stdout.channel.recv_exit_status()
        if as_dict:
            return {
                "code": return_code,
                "stdout": _stdout.read().decode("utf-8"),
                "stderr": _stderr.read().decode("utf-8")
            }
        else:
            return (
                return_code,
                _stdout.read().decode("utf-8"),
                _stderr.read().decode("utf-8")
            )

