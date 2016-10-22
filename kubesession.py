import requests
import ipaddress

from urllib.parse import urlparse
from requests.adapters import HTTPAdapter


class _KubernetesAdapter(HTTPAdapter):
    """
    A HTTPS Adapter for Python Requests that makes working with kubernetes API easier.

    It does the following special things:
        |
        - Replace 'kube://' with the server URL of the kubernetes master.
          This allows your code to call URLs like 'kube:///api/v1' rather
          than interpolate the URL of the master in all the places.
        - Replace the literal string '{namespace}' with the namespace parameter
          passed in. Again, to avoid having to interpolate the default everywhere.
        - For SSL checks, assert the hostname against what is passed in the
          Host: header, rather than whatever we are connecting to. This is only
          done if the Host: header is set explicitly. This should be used
          very carefully, since this could possibly be used as a security exploit.

    Do not use this directly, always call get_kubernetes_session instead.

    Adapted from the wonderful requests_toolbelt, specifically from
    https://github.com/sigmavirus24/requests-toolbelt/blob/master/requests_toolbelt/adapters/host_header_ssl.py
    """
    def __init__(self, server, namespace, **kwargs):
        super().__init__(**kwargs)
        self.server = server
        self.namespace = namespace

    def send(self, request, **kwargs):
        request.url = request.url.replace('kube://', self.server).replace('$$NAMESPACE$$', self.namespace)
        host_header = None
        # HTTP headers are case-insensitive (RFC 7230)
        for header in request.headers:
            if header.lower() == "host":
                host_header = request.headers[header]
                break

        connection_pool_kwargs = self.poolmanager.connection_pool_kw

        if host_header:
            connection_pool_kwargs["assert_hostname"] = host_header
        elif "assert_hostname" in connection_pool_kwargs:
            # an assert_hostname from a previous request may have been left
            connection_pool_kwargs.pop("assert_hostname", None)

        return super().send(request, **kwargs)


def get_kube_session(config, current_context=None, current_namespace='default', certificate_name='kubernetes'):
    if current_context is None:
        current_context = config['current-context']

    context = [c for c in config['contexts'] if c['name'] == current_context][0]['context']
    cluster = [c for c in config['clusters'] if c['name'] == context['cluster']][0]['cluster']
    if 'user' in context:  # Since user accounts aren't strictly required
        user = [u for u in config['users'] if u['name'] == context['user']][0]['user']
    else:
        user = {}

    s = requests.Session()
    s.mount('kube://', _KubernetesAdapter(cluster['server'], context.get('namespace', current_namespace)))

    # If we are using client certificates for authentication, set 'em!
    if 'client-certificate' in user:
        s.cert = (user['client-certificate'], user['client-key'])

    if 'token' in user:
        s.headers['Authorization'] = 'Bearer {token}'.format(token=user['token'])

    # TODO: Add support for Basic Auth!
    if cluster['server'].startswith('https://'):
        if cluster.get('insecure-skip-tls-verify', False):
            # Skip SSL verification completely if this option is set
            s.verify = False
            print('huh')
        else:
            # If we are using https *and* connecting to an IP, attempt to
            # validate for the name 'kubernetes' rather than just the IP.
            parts = urlparse(cluster['server'])
            try:
                ipaddress.ip_address(parts.hostname)
                print('blo')
                s.headers['Host'] = certificate_name
            except:
                # Not an IP address
                pass

            if 'certificate-authority' in cluster:
                s.verify = cluster['certificate-authority']
    return s
