# SPDX-FileCopyRightText: Copyright (c) 2023-present Jeffrey LeBlanc
# SPDX-License-Indentifier: MIT

import libvirt
from contextlib import contextmanager



class LibvirtSimInterface:

    def __init__(self, sim_prefix=None, uri='qemu:///system', shared_conn=None, quiet=True):
        assert sim_prefix is not None

        self.sim_prefix = sim_prefix
        self.uri = uri
        self.quiet = quiet

        if shared_conn is not None:
            self.conn = shared_conn
            self.shared_conn = True
        else:
            self.conn = None
            self.shared_conn = False
            self.connect()

    def _log(self, *args):
        if self.quiet: return

    def __del__(self):
        self._log('Being destroyed!')
        self.close()

    #-- Connection Handling ------------------------------------------------------#

    def connect(self):
        if not self.shared_conn and self.conn is None:
            try:
                self.conn = libvirt.open(self.uri)
            except libvirt.libvirtError:
                self.conn = None
                raise SystemExit("Unable to open connection to libvirt")

    def close(self):
        if not self.shared_conn and self.conn is not None:
            self._log('Closing the libvirt connection')
            self.conn.close()
            self.conn = None


    #-- Information Gathering ------------------------------------------------------#

    def get_network_information(self):
        results = {
            'inactive':[],
            'active':[]
        }
        network_names = self.conn.listNetworks()
        for network_name in network_names:
            network = self.conn.networkLookupByName(network_name)
            is_active = network.isActive()
            if is_active:
                results['active'].append({
                    'name': network_name,
                    'bridgeName': network.bridgeName(),
                    'is_active':True
                })
            else:
                results['inactive'].append({
                    'name': network_name,
                    'is_active':False
                })
        return results

    def get_domain_statuses(self):
        results = {
            'active': [],
            'inactive': []
        }

        domains = self.conn.listAllDomains(0)
        for domain in domains:
            domain_name = domain.name()
            if domain_name.startswith(self.sim_prefix):
                is_active = domain.isActive()
                if is_active:
                    results['active'].append(domain_name)
                else:
                    results['inactive'].append(domain_name)
            else:
                pass

        return results


    def get_active_network_info(self, include_ifaces=False):
        '''
        TODO: We will want to filter by sim prefix
        '''

        # Get the active domain ids
        active_domain_ids = self.conn.listDomainsID()

        # Iterate over them
        results = []
        for domain_id in active_domain_ids:
            try:
                domain = self.conn.lookupByID(domain_id)
                ifaces = _get_dom_ifaces(domain)
                ipv4_lst = _extract_ipv4(ifaces)
                info = dict(
                    libvirt_domain_id= domain_id,
                    libvirt_domain_name = domain.name(),
                    current_hostname = domain.hostname(),
                    current_ipv4_lst = ipv4_lst
                )
                if include_ifaces:
                    info['ifaces'] = ifaces
                results.append(info)
            except libvirt.libvirtError:
                print(f"Domain {domain_id} not found")

        return results

    #-- Control ------------------------------------------------------#

    def start_inactive_domains(self):
        for domain in self.conn.listAllDomains(0):
            domain_name = domain.name()
            if domain_name.startswith(self.sim_prefix):
                is_active = domain.isActive()
                if not domain.isActive():
                    print(f'starting {domain_name}...')
                    r = domain.create()
                    print('result: ',r)

    def shutdown_active_domains(self):
        for domain in self.conn.listAllDomains(0):
            domain_name = domain.name()
            if domain_name.startswith(self.sim_prefix):
                is_active = domain.isActive()
                if domain.isActive():
                    print(f'stopping {domain_name}...')
                    r = domain.shutdown()
                    print('result',r)


