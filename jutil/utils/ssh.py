# SPDX-FileCopyRightText: Copyright (c) 2023-present Jeffrey LeBlanc
# SPDX-License-Indentifier: MIT

import sh
import re
import os
import asyncio
import logging


def _get_permissions(fp):
    ''' Returns a integer '''
    return ( os.lstat(fp).st_mode & 0o777 )

class SSHConn():
    '''
    Convenience class to encapsulate an SSH connection.
    Master SSH Features will only work on Linux.
    Assumes SSH on port 22.
    '''

    def __init__(self, user, host, use_master=False, master_timeout_sec=15, tmux_session='devzone', tmux_window=0, strict_host=True):
        # Core attributes
        self.user = user
        self.host = host
        self.debug = False

        # Default tmux session
        self.tmux_session = tmux_session
        self.tmux_window = tmux_window
        self._ensure_default_tmux_sess = False

        # Master SSH
        self.using_master = use_master
        self.master_timeout_sec = master_timeout_sec
        self.master_config_path = os.path.join(os.environ['HOME'],'.ssh',f'MASTER_{self.host}.conf')
        self.master_socket_dir = os.path.join(os.environ['HOME'],'.ssh','sockets')

        # Setup and bake core call
        strhst = {} if strict_host else dict(o="StrictHostKeyChecking no")
        if self.using_master:
            self.setup_master_config()
            self.cli = sh.ssh.bake(f"{self.user}@{self.host}",F=self.master_config_path,**strhst)
        else:
            self.cli = sh.ssh.bake(f"{self.user}@{self.host}",**strhst)

    #-- Master Session Handling ------------------------------------------------------------------#

    def setup_master_config(self):
        '''
        Setup a ssh master configuration to reuse ssh connection
        '''

        # Make sure the socket directory exists and has proper permissions
        if not os.path.isdir(self.master_socket_dir):
            os.mkdir(self.master_socket_dir,mode=0o700)
        else:
            if _get_permissions(self.master_socket_dir) != 0o700:
                logging.warning(f'SSH Permission: {self.master_socket_dir} => 0o700')
                os.chmod(self.master_socket_dir, 0o700)

        # Make a custom config file for this host and set proper permissions
        config_contents = (
            '# Made automatically\n'
            f'Host {self.host}\n'
            'ControlMaster auto\n'
            f'ControlPath {self.master_socket_dir}/%r@%h-%p\n'
            f'ControlPersist {self.master_timeout_sec}\n' # time to live in seconds
        )
        if not os.path.isfile(self.master_config_path):
            sh.touch(self.master_config_path)
            os.chmod(self.master_config_path, 0o600)
            with open(self.master_config_path,'w') as f:
                f.write(config_contents)
        else:
            # Ensure proper permissions
            if _get_permissions(self.master_config_path) != 0o600:
                logging.warning(f'SSH Permission: {self.master_config_path} => 0o600')
                os.chmod(self.master_config_path, 0o600)
            # Ensure the config file has correct contents
            same = True
            with open(self.master_config_path,'r') as f:
                curr = f.read()
                same = ( curr == config_contents )
            if not same:
                with open(self.master_config_path,'w') as f:
                    logging.warning(f'SSH Control: updating contents of {self.master_config_path}')
                    f.write(config_contents)

    def remove_master_config(self):
        ''' Use with caution! May strand other processes using the configuration '''

        # If the relevant socket exists, delete it
        socket_path = os.path.join(self.master_socket_dir,f'{self.user}@{self.host}-22')
        if os.path.exists(socket_path):
            os.remove(socket_path)
        # Remove the config file
        if os.path.isfile(self.master_config_path):
            os.remove(self.master_config_path)


    #-- Command Handling ------------------------------------------------------------------#

    def send(self, command_string, quiet=True):
        if self.debug and not quiet:
            print('-> sending: ',command_string)
        o = self.cli(command_string)
        return (o.stdout.decode('utf-8'),o.stderr.decode('utf-8'))

    def send_success(self, command_string, yn=None, quiet=True):
        if yn is None: yn = ' > /dev/null 2>&1 && echo Y || echo N'
        o,e = self.send(f'{command_string} {yn}',quiet=quiet)
        return (o.strip() == 'Y')

    def sendraw(self, command_string):
        try:
            resp = self.cli(command_string)
            o = resp.stdout.decode('utf-8').strip()
            e = resp.stderr.decode('utf-8').strip()
            c = resp.exit_code
        except sh.ErrorReturnCode as err:
            o = err.stdout.decode('utf-8').strip()
            e = err.stderr.decode('utf-8').strip()
            c = err.exit_code
        return c,o,e

    #-- Sync Handling ------------------------------------------------------------------#

    def rsync(self, src, dst, ensure_dst_root=True, delete=True):
        if not dst.startswith('/'):
            raise Exception('Rsync dst path must be absolute')

        if ensure_dst_root:
            c,o,e = self.sendraw(f'mkdir -p {dst}')

        cmdlst = ['-avz','--exclude','.git/','--exclude','__pycache__/']
        if self.using_master:
            cmdlst += ['-e',f"ssh -o 'ControlPath={self.master_socket_dir}/%r@%h-%p'"]
        if delete:
            cmdlst += ['--delete']
        cmdlst += [src, f'{self.user}@{self.host}:{dst}' ]
        return sh.rsync(*cmdlst)

    def scp(self, src, dst):
        cmd = [src,f'{self.user}@{self.host}:{dst}']
        if self.using_master:
            cmd = ['-F',self.master_config_path] + cmd
        out = sh.scp(cmd)

    #-- TMUX Handling ------------------------------------------------------------------#

    def has_tmux_session(self, session_name=None):
        # There is a better tmux command to do this
        if session_name is None:
            session_name = self.tmux_session
        c,o,e = self.sendraw('tmux ls')
        if c != 0: return False
        return ( re.search(f'{session_name}: \d+ windows',o) is not None )

    def ensure_tmux_session(self, session_name=None):
        if session_name is None:
            session_name = self.tmux_session
        if not self.has_tmux_session(session_name):
            self.send(f'tmux new -d -s {session_name}')
            print('-> {session_name} tmux session MADE')

        if session_name == self.tmux_session:
            self._ensure_default_tmux_sess = True

    def send_tmux_keys(self, key_string, wrap=True):
        if not self._ensure_default_tmux_sess:
            self.ensure_tmux_session()

        tmuxkey = f'{self.tmux_session}.{self.tmux_window}'
        enter = 'ENTER' if wrap else ''
        command = rf'tmux send-keys -t {tmuxkey} "{key_string}" {enter}'
        if self.debug:
            print('-> sending tmux keys: ',key_string)
        return self.send(command)

    async def send_tmux_keys_seq(self, seq, wrap=True, delay=0.25):
        for cmd in seq:
            o,e = self.send_tmux_keys(cmd,wrap=wrap)
            await asyncio.sleep(delay)

    def capture_tmux_scrollback(self, lines=32768):
        tmuxkey = f'{self.tmux_session}.{self.tmux_window}'
        cmd = f'tmux capture-pane -t {tmuxkey} -J -pS -{lines}'
        return self.send(cmd)

    def send_tmux_ctrl_c(self):
        o,e = self.send_tmux_keys('"C-c"')

    #-- Other Utilties --------------------------------------------------------------#

    def remote_dir_contents(self, dirpath):
        c,o,e = self.sendraw(f'ls -1 {dirpath}')
        if c != 0:
            return None
        lst = o.split('\n')
        if '' in lst: lst.remove('')
        return lst


