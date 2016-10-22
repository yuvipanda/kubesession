"""
This is the entire unit test suite for kubesession!
We do unfortunately hammer example.com with requests, since there isn't
a very good way to mock our use of requests here. requests_mock doesn't
work since we too rely on a Adapter.
"""
import requests
from kubesession import get_kube_session


def make_test_config(contexts, clusters, users, current_context):
    """
    Return a KubeConfig dict constructed with the given info
    
    All parameters are required.
    """
    return {
        'apiVersion': 'v1', 'kind': 'Config',
        'clusters': [{'name': key, 'cluster': value} for key, value in clusters.items()],
        'contexts': [{'name': key, 'context': value} for key, value in contexts.items()],
        'users': [{'name': key, 'user': value} for key, value in users.items()],
        'current-context': current_context
    }


# In[7]:

SERVER = 'http://httpbin.org:80/get'
HTTPS_SERVER = 'https://httpbin.org:80/get'

def test_tokenauth():
    """
    Test that a config with token auth works as it should
    """
    config = make_test_config(
        {'minikube': {'cluster': 'minikube', 'user': 'minikube'}},
        {'minikube': {'server': SERVER}},
        {'minikube': {'token': 'something'}},
        'minikube'
    )
    session = get_kube_session(config)
    assert 'Host' not in session.headers
    r = session.request('GET', 'kube:///api/v1')
    assert r.url.startswith(SERVER)
    assert r.request.headers['Authorization'] == 'Bearer something'


def test_simple_config():
    """
    Test that a simple config without any authentication
    """
    config = make_test_config(
        {'minikube': {'cluster': 'minikube'}},
        {'minikube': {'server': SERVER}},
        {},
        'minikube'
    )
    session = get_kube_session(config)
    assert 'Host' not in session.headers
    r = session.request('GET', 'kube:///api/v1')
    assert r.url.startswith(SERVER)
    assert 'Authorization' not in r.request.headers


def test_custom_ca():
    """
    Test that a custom CA is respected when required
    """
    config = make_test_config(
        {'minikube': {'cluster': 'minikube'}},
        {'minikube': {'server': HTTPS_SERVER, 'certificate-authority': '/dev/null'}},
        {},
        'minikube'
    )
    session = get_kube_session(config)
    assert session.verify == '/dev/null'


def test_custom_ca_ignore():
    """
    Test that a custom CA is ignored when using HTTP
    """
    config = make_test_config(
        {'minikube': {'cluster': 'minikube'}},
        {'minikube': {'server': SERVER, 'certificate-authority': '/dev/null'}},
        {},
        'minikube'
    )
    session = get_kube_session(config)
    assert session.verify != '/dev/null'


def test_insecure_tls():
    """
    Test that we can hit HTTPS with certificate errors when insecure TLS is set
    """
    config = make_test_config(
        {'minikube': {'cluster': 'minikube'}},
        {'minikube': {'server': HTTPS_SERVER, 'certificate-authority': '/dev/null', 'insecure-skip-tls-verify': True}},
        {},
        'minikube'
    )
    session = get_kube_session(config)
    assert session.verify == False


def test_ip_rewrite():
    """
    Test that if we're using an IP to connect, Host header is set
    """
    config = make_test_config(
        {'minikube': {'cluster': 'minikube', 'namespace': 'testnamespace'}},
        {'minikube': {'server': 'https://23.22.14.18'}},
        {},
        'minikube'
    )
    session = get_kube_session(config, certificate_name='httpbin.org')
    r = session.request('GET', 'kube:///api/v1')

    assert r.request.headers['Host'] == 'httpbin.org'

def test_namespace_expansion():
    """
    Test that $$NAMESPACE$$ expands to the current namespace
    """
    config = make_test_config(
        {'minikube': {'cluster': 'minikube', 'namespace': 'testnamespace'}},
        {'minikube': {'server': SERVER}},
        {},
        'minikube'
    )
    session = get_kube_session(config)
    r = session.request('GET', 'kube:///api/v1/$$NAMESPACE$$/pods')
    assert r.url == '{SERVER}/api/v1/testnamespace/pods'.format(SERVER=SERVER)


