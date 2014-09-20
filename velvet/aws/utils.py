import boto.iam

def upload_server_cert(cert_name, cert_file, private_key_file, cert_chain_file):

    cert_body = None
    private_key = None
    cert_chain = None

    print cert_file
    with open(cert_file) as f:
        cert_body = f.read()
    if cert_body is None or len(cert_body) < 10:
        raise Exception('Could not read the private key file')

    print private_key_file
    with open(private_key_file) as f:
        private_key = f.read()
    if private_key is None or len(private_key) < 10:
        raise Exception('Could not read the private key file')

    print cert_chain_file
    with open(cert_chain_file) as f:
        cert_chain = f.read()
    if cert_chain is None or len(cert_chain) < 10:
        raise Exception('Could not read the private key file')

    c = boto.iam.connect_to_region('universal')
    c.upload_server_cert(cert_name, cert_body, private_key, cert_chain)

    certs = c.get_all_server_certs()
    print certs


def list_server_cert():

    c = boto.iam.connect_to_region('universal')
    certs = c.get_all_server_certs()
    print certs

