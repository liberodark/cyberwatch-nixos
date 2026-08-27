#!/usr/bin/env python3
# coding: utf-8

import base64
import hashlib
import hmac
import json
import email.utils
import traceback
import socket
import sys

from cyberwatch_agent import APP_VERSION, APP_PACKAGE, APP_NAME, COMPANY_NAME
from cyberwatch_agent.system_info import OperatingSystem

## Utilisation des bibliothèque python locales sur MacOS.
## Les bibliothèques sont stockées dans le sous-dossier python_pkgs/
## Ajout du Python Path qui contient les dépendances nécessaires à
## cyberwatch-agent sur MacOS en se basant sur le chemin du fichier actuel.
if OperatingSystem().Mac:
    try:
        from pathlib import Path
        file_path = Path(__file__)
        python_pkgs_dir = file_path.parent / "python_pkgs"
        sys.path.append(str(python_pkgs_dir))

        import requests
        import urllib3
        import urllib.parse as urlparse
    except ModuleNotFoundError as error:
        traceback.print_exc()
        sys.exit(1)

try:
    import requests
    import urllib3
    import urllib.parse as urlparse
except (ModuleNotFoundError, ImportError) as error:
    traceback.print_exc()
    sys.exit(1)

urllib3.disable_warnings()

DEFAULT_HEADERS = {'Content-Type': 'application/json',
                   'Accept': 'application/json',
                   'Accept-Encoding': 'gzip',
                   'User-Agent': '/'.join([APP_NAME, APP_VERSION, APP_PACKAGE])}

# Timeout if connection establishment is longer than *first argument* seconds,
# and if no bytes are received during *second argument* seconds.
# ref: https://docs.python-requests.org/en/master/user/advanced/#timeouts
API_REQUEST_TIMEOUT = (60, 60)


class SslContextHttpAdapter(requests.sessions.HTTPAdapter):
    """Transport adapter that allows us to use system-provided SSL
    certificates.

    The urllib3 module supports the use of SSLContext via the `context` keyword,
    but the requests.{get,put,post} methods don't. This class can modify the
    SSLContext for a requests session.

    Usage:

    ```
    system_ssl_adapter = SslContextHttpAdapter()
    session.mount("https://", system_ssl_adapter)
    ```
    """

    def init_poolmanager(self, *args, **kwargs):
        import ssl

        ssl_context = ssl.create_default_context()
        ssl_context.load_default_certs()
        kwargs["ssl_context"] = ssl_context
        return super(SslContextHttpAdapter, self).init_poolmanager(*args, **kwargs)


class ApiClient(object):
    def __init__(self, configuration, logger, key_id=None, secret_key=None):
        self.key_id = key_id or configuration.api.access_key_id
        self.secret_key = secret_key or configuration.api.secret_access_key
        self.conf = configuration
        self.logger = logger
        self.http_session = requests.Session()
        self.http_session.headers = DEFAULT_HEADERS

        if configuration.api.allow_selfsigned:
            self.http_session.verify = False
        else:
            # Add a wrapper to the HTTP session to use systems certificates.
            # This is incompatible with `self.http_session.verify = False`
            # because of the internal of the SSLContext object.
            self.http_session.mount("https://", SslContextHttpAdapter())

        if configuration.proxy.enabled:
            self.http_session.trust_env = False
            self.http_session.proxies = configuration.proxy.hosts

    def ping(self):
        response = self._make_request('GET', 'ping')
        if response:
            ping = self._parse_json(response.text)
            if ping:
                return True

    def create_server(self, server_info):
        response = self._make_request('POST', 'agents',
                                      data=json.dumps(server_info))
        if response:
            server = self._parse_json(response.text)
            if server:
                return server

    def get_tasks(self):
        response = self._make_request('GET', 'agents/tasks')
        if response:
            tasks = self._parse_json(response.text)
            if tasks:
                return tasks

    def get_script(self, id_):
        response = self._make_request('GET', 'agents/scripts/{0}'.format(id_))
        if response:
            script = self._parse_json(response.text)

            if not script:
                return
            if not script.get('contents'):
                self.logger.error('Missing script contents.')
            else:
                if self.conf.env.os.Linux:
                    script['contents'] = script['contents'].replace("\r", '')
                return script

    def update_script(self, id_, script_info):
        response = self._make_request('PUT', 'agents/scripts/{0}'.format(id_),
                                      data=json.dumps(script_info))
        if response:
            return True

    def crash_report(self, data):
        self.logger.error(f"Crash report:\n{data}")
        headers = {'Content-Type': 'text/plain',
                   'Accept': 'text/plain'}
        response = self._make_request('POST', 'crash_report', data, headers)
        if response:
            return True

    def _parse_json(self, json_string):
        try:
            obj = json.loads(json_string)
            return obj
        except ValueError:
            self.logger.error('Failed to parse JSON response.')

    def _make_request(self, method, api_route, data=None, headers=None):
        api_url = self.conf.api.base_url
        requested_url = urlparse.urljoin(api_url if api_url.endswith('/') else f"{api_url}/", api_route)
        request = requests.Request(method.upper(),
                                   requested_url,
                                   data=data,
                                   headers=headers)
        return self.send_request(request)

    # Sign HTTP request
    def sign_request(self, request):
        request.data = request.data or str()
        request.headers['Date'] = email.utils.formatdate(usegmt=True)
        request.headers['X-AUTHORIZATION-CONTENT-SHA256'] = (base64.b64encode(hashlib.sha256(request.data.encode('utf-8')).digest())).decode()

        url_parts = urlparse.urlsplit(request.url)
        path = '?'.join([url_parts.path,
                         url_parts.query]) if url_parts.query else url_parts.path

        canonical_list = [request.method,
                          self.http_session.headers['Content-Type'],
                          request.headers['X-AUTHORIZATION-CONTENT-SHA256'],
                          path,
                          request.headers['Date']]

        if 'X-Cbw-IP' in request.headers:
            canonical_list.append(request.headers['X-Cbw-IP'])

        canonical = ','.join(canonical_list)

        signature = (base64.b64encode(
            hmac.new(self.secret_key.encode('utf-8'), canonical.encode('utf-8'),
                     hashlib.sha256).digest())).decode()

        request.headers['Authorization'] = '{0} APIAuth-HMAC-SHA256 {1}:{2}'.format(COMPANY_NAME,
                                                                                    self.key_id,
                                                                                    signature)

        return request

    def forward_ip(self, request):
        local_ip = self._get_ip_address()

        if local_ip is not None:
            request.headers['X-Cbw-IP'] = local_ip

        return request

    # Send HTTP request
    def send_request(self, request):
        request = self.forward_ip(request)
        request = self.sign_request(request)

        response = None

        # Prepare request
        try:
            prepared_request = self.http_session.prepare_request(request)
        except urllib3.exceptions.LocationParseError as e:
            self.logger.error(
                'HTTP: LocationParseError: {0}'.format(str(e)))
            return response

        # Send request
        try:
            response = self.http_session.send(prepared_request, timeout=API_REQUEST_TIMEOUT)

            # Check for API errors
            if not response:
                try:
                    error = json.loads(response.text).get('error')
                    self.logger.error('API Error: {0}/{1}: {2}'
                                      .format(error.get('code'),
                                              error.get('status'),
                                              error.get('message')))
                except ValueError:
                    self.logger.error('API Error: Malformed JSON Error. Status: {0}'
                                      .format(response.status_code))

        # Check for transport errors
        except requests.exceptions.ConnectionError as e:
            try:
                self.logger.error('HTTP: ConnectionError: {0}'.format(e.args[0].reason))
            except AttributeError:
                self.logger.error('HTTP: ConnectionError: {0}'.format(str(e)))

        except requests.exceptions.HTTPError as e:
            self.logger.error('HTTP: Invalid response: {0}'.format(str(e)))

        except requests.exceptions.Timeout as e:
            self.logger.error('HTTP: Timeout: {0}'.format(str(e)))

        except requests.exceptions.TooManyRedirects as e:
            self.logger.error('HTTP: TooManyRedirects: {0}'.format(str(e)))

        except ValueError as e:
            if e.args[0] == "check_hostname requires server_hostname":
                self.logger.error(f"ValueError while sending request: {e}. You requested to verify the certificate of the server, however, "
                "python could not identify its domain name. Please make sure that the value of field 'base_url' in "
                "file 'agent.conf' uses a domain name and not an IP adress.")
            else:
                raise e

        return response

    @staticmethod
    def _get_ip_address():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            s.connect(("46.105.40.168", 80))
            ip_address = s.getsockname()[0]
            s.close()
            return ip_address
        except:
            s.close()
            return None
