# SPDX-FileCopyRightText: Copyright (c) 2023-present Jeffrey LeBlanc
# SPDX-License-Indentifier: MIT

import libvirt
from contextlib import contextmanager


def can_user_control_libvirt(exit_if_not=False):
    import os
    # Check if we are root
    euid = os.geteuid()
    if euid == 0:
        return True

    # If not root, see if user is in kvm and libvirt groups
    import getpass
    import grp
    username = getpass.getuser()
    try:
        kvmg = grp.getgrnam('kvm')
        libvirtg = grp.getgrnam('libvirt')
        if username in kvmg.gr_mem and username in libvirtg.gr_mem:
            return True
    except:
        pass

    if exit_if_not:
        print('Should be run as root, with sudo, or as user in libvirt and kvm groups')
        exit(1)
    else:
        return False


IPTYPE = {
    libvirt.VIR_IP_ADDR_TYPE_IPV4: "ipv4",
    libvirt.VIR_IP_ADDR_TYPE_IPV6: "ipv6",
}

def _get_dom_ifaces(dom):
    ifaces = dom.interfaceAddresses(libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE)
    if ifaces is None:
        print("Failed to get domain interfaces")
        return None
    return ifaces

def _extract_ipv4(ifaces):
    # Note this could be done better I'm sure, esp. the check on if ip is ipv4
    ipv4_lst = []
    if ifaces is not None:
        for iface in ifaces.values():
            if 'addrs' in iface:
                for addr in iface['addrs']:
                    ip = addr.get('addr','')
                    if ip != '' and ip.count('.'):
                        ipv4_lst.append(ip)
    return ipv4_lst

@contextmanager
def libvirt_connection(uri='qemu:///system', quiet=False):
    try:
        conn = libvirt.open(uri)
    except libvirt.libvirtError:
        raise SystemExit("Unable to open connection to libvirt")
    if not quiet: print('-> libvirt connection UP')
    yield conn
    conn.close()
    if not quiet: print('-> libvirt connection CLOSED')

