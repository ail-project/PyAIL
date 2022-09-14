# -*- coding: utf-8 -*-

import json
import logging
import requests
import sys
import traceback

from datetime import date, datetime
from urllib.parse import urljoin

from . import __version__, everything_broken
from .core import encode_and_compress_data, get_data_sha256, ail_json_default
from .exceptions import PyAILError, MissingDependency, NoURL, NoKey, PyAILInvalidFormat, AILServerError, PyAILNotImplementedYet, PyAILUnexpectedResponse, PyAILEmptyResponse

logger = logging.getLogger('pyail')

class PyAIL:
    """Python API for AIL

    :param url: URL of the AIL instance you want to connect to
    :param key: API key of the user you want to use
    :param ssl: can be True or False (to check or to not check the validity of the certificate. Or a CA_BUNDLE in case of self signed or other certificate (the concatenation of all the *.crt of the chain)
    :param debug: Write all the debug information to stderr
    :param api_version: Version of the API used (only the v1 is currently available)
    :param proxies: Proxy dict as describes here: http://docs.python-requests.org/en/master/user/advanced/#proxies
    :param cert: Client certificate, as described there: http://docs.python-requests.org/en/master/user/advanced/#client-side-certificates
    :param auth: The auth parameter is passed directly to requests, as described here: http://docs.python-requests.org/en/master/user/authentication/
    :param tool: The software using PyAIL (string), used to set a unique user-agent
    :param timeout: Timeout as described here: https://requests.readthedocs.io/en/master/user/advanced/#timeouts
    """

    def __init__(self, url, key, ssl=True, debug=False, api_version='v1', proxies={}, cert=None, auth=None, tool=None, timeout=None):
        if not url:
            raise NoURL('Please provide the URL of your AIL instance.')
        if not key:
            raise NoKey('Please provide your authorization key.')

        self.root_url = url
        self.key = key
        self.ssl = ssl
        self.api_version = api_version
        self.proxies = proxies
        self.cert = cert
        self.auth = auth
        self.tool = tool
        self.timeout = timeout

        if debug:
            logger.setLevel(logging.DEBUG)
            logger.info('To configure logging in your script, leave it to None and use the following: import logging; logging.getLogger(\'pyail\').setLevel(logging.DEBUG)')

        if not self.ssl:
            from requests.packages.urllib3.exceptions import InsecureRequestWarning
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        try:
            # Make sure the AIL instance is working and the URL is valid
            # # TODO: check version compatibility

            self.ping_ail()

        except Exception as e:
            traceback.print_exc()
            raise PyAILError(f'Unable to connect to AIL ({self.root_url}). Please make sure the API key and the URL are correct (https is required): {e}')

    # # TODO: verify version compatibility between AIL and pyAIL

    ## BEGIN Server test ##

    def ping_ail(self):
        response = self._prepare_request('GET', f'api/{self.api_version}/ping')
        return self._check_json_response(response)

    ## -- END Server test -- ##

    ## BEGIN Feed AIL ##
    def feed_json_item(self, data, meta, source, source_uuid, default_encoding='UTF-8'):
        dict_to_send = {}
        dict_to_send['data'] = encode_and_compress_data(data)
        dict_to_send['data-sha256'] = get_data_sha256(data)
        dict_to_send['meta'] = meta
        dict_to_send['source'] = source
        dict_to_send['source_uuid'] = source_uuid
        dict_to_send['default_encoding'] = default_encoding
        response = self._prepare_request('POST', f'api/{self.api_version}/import/json/item', data=dict_to_send)
        return self._check_json_response(response)

    # feed json file  -------------------

    # # TODO: return task uuid + add check status
    # Crawler #
    def crawl_url(self, url, har=False, screenshot=False, depth_limit=1):
        dict_to_send = {}
        dict_to_send['url'] = url
        dict_to_send['har'] = har
        dict_to_send['screenshot'] = screenshot
        dict_to_send['depth_limit'] = int(depth_limit)
        response = self._prepare_request('POST', f'api/{self.api_version}/add/crawler/task', data=dict_to_send)
        return self._check_json_response(response)

    ## -- END Feed AIL -- ##



    ## Internal methods ###

    def _check_json_response(self, response):
        r = self._check_response(response, expect_json=True)
        if isinstance(r, (dict, list)):
            return r
        else:
            raise PyAILUnexpectedResponse('Invalid JSON received.')


    def _check_response(self, response, expect_json=False):
        """Check if the response from the server is not an unexpected error"""
        if response.status_code >= 500:
            logger.critical(everything_broken.format(response.request.headers, response.request.body, response.text))
            raise AILServerError(f'Error code 500:\n{response.text}')

        if 400 <= response.status_code < 500:
            # The server returns a json message with the error details
            try:
                error_message = response.json()
            except Exception:
                raise AILServerError(f'Error code {response.status_code}:\n{response.text}')

            logger.error(f'Something went wrong ({response.status_code}): {error_message}')
            return {'errors': (response.status_code, error_message)}

        # At this point, we had no error.

        try:
            response_json = response.json()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(response_json)
            if isinstance(response_json, dict) and response_json.get('response') is not None:
                # Cleanup.
                response_json = response_json['response']
            return response_json
        except Exception:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(response.text)
            if expect_json:
                raise PyAILUnexpectedResponse(f'Unexpected response from server: {response.text}')
            if not response.content:
                # Empty response
                logger.error('Got an empty response.')
                return {'errors': 'The response is empty.'}
            return response.text

    def _prepare_request(self, request_type, url, data={}, params={}, output_type='json'):
        '''Prepare a request for python-requests'''
        url = urljoin(self.root_url, url)
        if data == {} or isinstance(data, str):
            d = data
        elif data:
            if not isinstance(data, str):  # Else, we already have a text blob to send
                if isinstance(data, dict):  # Else, we can directly json encode.
                    # Remove None values.
                    data = {k: v for k, v in data.items() if v is not None}
                d = json.dumps(data, default=ail_json_default)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'{request_type} - {url}')
            if d is not None:
                logger.debug(d)

        req = requests.Request(request_type, url, data=d, params=params)
        with requests.Session() as s:
            user_agent = f'PyAIL {__version__} - Python {".".join(str(x) for x in sys.version_info[:2])}'
            if self.tool:
                user_agent = f'{user_agent} - {self.tool}'
            req.auth = self.auth
            prepped = s.prepare_request(req)
            prepped.headers.update(
                {'Authorization': self.key,
                 'Accept': f'application/{output_type}',
                 'content-type': f'application/{output_type}',
                 'User-Agent': user_agent})
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(prepped.headers)
            settings = s.merge_environment_settings(req.url, proxies=self.proxies or {}, stream=None, verify=self.ssl, cert=self.cert)
            return s.send(prepped, timeout=self.timeout, **settings)

    def __repr__(self):
        return f'<{self.__class__.__name__}(url={self.root_url})'
