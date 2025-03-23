# SPDX-FileCopyRightText: Copyright (c) 2022-present Jeffrey LeBlanc
# SPDX-License-Indentifier: MIT

from .proc import proc, proc0

def host_cert_exts(host):
    return f"""basicConstraints=CA:FALSE
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
subjectAltName=DNS:{host}
"""

class PKIGenerator:

    def __init__(self, pki_dir):
        assert pki_dir.is_dir()
        self.PKI_DIR = pki_dir

    def generate_site_ca(self, ca_name="Fake Root CA", numbits="2048", days=400):
        ca_key = self.PKI_DIR/"ca.key"
        ca_pem = self.PKI_DIR/"ca.pem"

        if not ca_key.is_file():
            proc0([
                "openssl","genrsa",
                "-out",ca_key,
                numbits
            ])

        if not ca_pem.is_file():
            proc0([
                "openssl","req",
                "-x509",
                "-key", ca_key,
                "-subj", f"/CN={ca_name}",
                "-days", str(days),
                "-extensions", "v3_ca",
                "-out", ca_pem,
                # Needed in newer versions of openssl and python ssl implementation
                "-addext","keyUsage=critical,digitalSignature,keyCertSign"
            ])


    def generate_host_cert(self, hostname, adl_subj="", prefix="",numbits="2048",days=400,*,force=False):
        if prefix != "" and not prefix.endswith("_"):
            prefix = prefix+"_"

        # Pickup our ca
        ca_key = self.PKI_DIR/"ca.key"
        ca_pem = self.PKI_DIR/"ca.pem"
        assert ( ca_key.is_file() and ca_pem.is_file() )

        # Generate hostfile paths
        phostname = f"{prefix}{hostname}"
        hostfile_key = self.PKI_DIR/f"{phostname}.key"
        hostfile_pem = self.PKI_DIR/f"{phostname}.pem"
        hostfile_csr = self.PKI_DIR/f"{phostname}.csr"
        extfile =      self.PKI_DIR/f"{phostname}-extfile.cnf"

        if force or ( not ( hostfile_key.is_file() and hostfile_pem.is_file() ) ):
            # Build the private key
            proc0([
                "openssl","genrsa",
                "-out", str(hostfile_key),
                numbits
            ])

            # Generate the csr
            c,csr_text,e = proc0([
                "openssl","req",
                "-new",
                "-subj", f"{adl_subj}/CN={hostname}",
                "-key", hostfile_key
            ])
            hostfile_csr.write_text(csr_text)

            # Build the extensions file
            extfile.write_text(host_cert_exts(hostname))

            print("DAYS!!!!?????",days)

            # Create the signed certificate
            proc0([
                "openssl","x509",
                "-req",
                "-in", hostfile_csr,
                "-CAkey", ca_key,
                "-CA", ca_pem,
                "-CAcreateserial",
                "-out", hostfile_pem,
                "-days", str(days),
                "-extfile", extfile
            ])

