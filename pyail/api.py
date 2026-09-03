# -*- coding: utf-8 -*-

import json
import logging
import os
import requests
import re
import shutil
import sys
import tempfile
import time
import traceback
import unicodedata

from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin
from uuid import uuid4

from . import __version__, everything_broken
from .core import encode_and_compress_data, get_data_sha256, ail_json_default
from .exceptions import PyAILError, MissingDependency, NoURL, NoKey, PyAILInvalidFormat, AILServerError, PyAILNotImplementedYet, PyAILUnexpectedResponse, PyAILEmptyResponse

logger = logging.getLogger('pyail')

# class AbstractAIL

# class Investigation:
#     def __init__(self, investigation_uuid):
#         self.uuid = investigation_uuid
#
#
# class AILObject:
#     def __init__(self, obj_type, obj_subtype, obj_id):
#         self.type = obj_type
#         self.subtype = obj_subtype
#         self.id = obj_id
#
#         # first_seen
#         # last_seen
#
#     # def add_tag(self, tag):


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

            self.ping()

        except Exception as e:
            if debug:
                traceback.print_exc()
            raise PyAILError(f'Unable to connect to AIL ({self.root_url}). Please make sure the API key and the URL are correct (https is required): {e}')

    # # TODO: verify version compatibility between AIL and pyAIL

    #### AIL Server ####

    def ping_ail(self):
        print('WARNING DEPRECATED: Please use ping()')
        return self.ping()

    def ping(self):
        response = self._prepare_request('GET', f'api/{self.api_version}/ping')
        return self._check_json_response(response)

    def get_uuid(self):
        response = self._prepare_request('GET', f'api/{self.api_version}/uuid')
        return self._check_json_response(response)

    def get_version(self):
        response = self._prepare_request('GET', f'api/{self.api_version}/version')
        return self._check_json_response(response)

    #### Chats ####

    def get_chat_instances(self, page=1, page_size=50):
        """List chat instances available to the authenticated user.

        The returned dictionary contains ``instances`` and ``pagination``.
        Pagination values are passed to AIL, which applies the limits and
        normalization defined by the server API.

        :param page: One-based result page to request.
        :type page: int
        :param page_size: Maximum number of instances to request per page.
        :type page_size: int
        :return: The instance collection and its pagination metadata.
        :rtype: dict
        """
        params = {'page': page, 'page_size': page_size}
        response = self._prepare_request(
            'GET', f'api/{self.api_version}/chat/instances', params=params
        )
        return self._check_json_response(response)

    def get_chats(self, instance_uuid, languages=None, page=1, page_size=50):
        """List chats belonging to a chat instance.

        The returned dictionary contains the instance metadata, a ``chats``
        collection, and pagination metadata. Language tags are not validated
        or normalized by PyAIL. A comma-separated string is sent as one query
        value, while a sequence is encoded by Requests as repeated values.

        :param instance_uuid: UUID of the chat instance to inspect.
        :type instance_uuid: str
        :param languages: Optional BCP 47 language tag or tags, expressed as a
            comma-separated string or a sequence.
        :type languages: str or sequence or None
        :param page: One-based result page to request.
        :type page: int
        :param page_size: Maximum number of chats to request per page.
        :type page_size: int
        :return: The instance metadata, chats, and pagination metadata.
        :rtype: dict
        """
        params = self._chat_query_params(page, page_size, languages)
        response = self._prepare_request(
            'GET',
            f'api/{self.api_version}/chat/instances/{instance_uuid}/chats',
            params=params,
        )
        return self._check_json_response(response)

    def get_chat_messages(self, instance_uuid, id, languages=None,
                          page=1, page_size=500):
        """Retrieve one page of messages attached directly to a chat.

        Messages belonging to subchannels or threads are not included. Use
        :meth:`get_chat_content` to retrieve a complete chat hierarchy.

        :param instance_uuid: UUID of the chat instance.
        :type instance_uuid: str
        :param id: Original, unsanitized chat identifier returned by AIL.
        :type id: str
        :param languages: Optional comma-separated language string or sequence
            of BCP 47 tags. Values are forwarded unchanged to AIL.
        :type languages: str or sequence or None
        :param page: One-based message page to request.
        :type page: int
        :param page_size: Maximum number of messages to request per page.
        :type page_size: int
        :return: Chat metadata, direct messages, and pagination metadata.
        :rtype: dict
        """
        return self._get_chat_container_messages(
            'chat/messages', instance_uuid, id, languages, page, page_size
        )

    def get_chat_subchannel_messages(self, instance_uuid, id,
                                     languages=None, page=1, page_size=500):
        """Retrieve one page of messages attached directly to a subchannel.

        Messages belonging to the subchannel's threads are not included.

        :param instance_uuid: UUID of the chat instance.
        :type instance_uuid: str
        :param id: Original subchannel identifier returned in chat metadata.
        :type id: str
        :param languages: Optional comma-separated language string or sequence
            of BCP 47 tags. Values are forwarded unchanged to AIL.
        :type languages: str or sequence or None
        :param page: One-based message page to request.
        :type page: int
        :param page_size: Maximum number of messages to request per page.
        :type page_size: int
        :return: Subchannel metadata, direct messages, and pagination metadata.
        :rtype: dict
        """
        return self._get_chat_container_messages(
            'chat/subchannel/messages', instance_uuid, id, languages, page,
            page_size
        )

    def get_chat_thread_messages(self, instance_uuid, id,
                                 languages=None, page=1, page_size=500):
        """Retrieve one page of messages attached directly to a thread.

        :param instance_uuid: UUID of the chat instance.
        :type instance_uuid: str
        :param id: Original thread identifier returned in container metadata.
        :type id: str
        :param languages: Optional comma-separated language string or sequence
            of BCP 47 tags. Values are forwarded unchanged to AIL.
        :type languages: str or sequence or None
        :param page: One-based message page to request.
        :type page: int
        :param page_size: Maximum number of messages to request per page.
        :type page_size: int
        :return: Thread metadata, direct messages, and pagination metadata.
        :rtype: dict
        """
        return self._get_chat_container_messages(
            'chat/thread/messages', instance_uuid, id, languages, page,
            page_size
        )

    @staticmethod
    def _chat_query_params(page, page_size, languages=None, **params):
        params.update({'page': page, 'page_size': page_size})
        if languages is not None:
            params['languages'] = languages
        return params

    def _get_chat_container_messages(self, endpoint, instance_uuid,
                                     container_id, languages, page, page_size):
        # Container identifiers deliberately remain query parameters: source
        # identifiers can contain slashes and must not become URL path parts.
        params = self._chat_query_params(
            page, page_size, languages,
            instance_uuid=instance_uuid,
            id=container_id,
        )
        response = self._prepare_request(
            'GET', f'api/{self.api_version}/{endpoint}', params=params
        )
        return self._check_json_response(response)

    def get_chat_content(self, instance_uuid, id, languages=None,
                         page_size=500):
        """Retrieve a complete chat hierarchy from AIL.

        This method downloads every page independently for the chat, each
        subchannel, each thread attached directly to the chat, and each thread
        attached to a subchannel. Message arrays retain the order supplied by
        AIL. The result is returned in memory and is not written to disk.

        :param instance_uuid: UUID of the chat instance.
        :type instance_uuid: str
        :param id: Original, unsanitized chat identifier returned by AIL.
        :type id: str
        :param languages: Optional comma-separated language string or sequence
            of BCP 47 tags. The same value is forwarded unchanged to every
            message request.
        :type languages: str or sequence or None
        :param page_size: Maximum number of messages requested for each page.
        :type page_size: int
        :return: Complete chat metadata, messages, subchannels, and threads.
        :rtype: dict
        :raises AILServerError: If AIL rejects a request during traversal.
        :raises PyAILUnexpectedResponse: If AIL returns an invalid chat payload.
        """
        chat, messages = self._get_all_container_messages(
            self.get_chat_messages, 'chat', instance_uuid, id,
            languages, page_size
        )

        result = {
            'chat': chat,
            'messages': messages,
            'subchannels': [],
            'threads': [],
        }
        for child in chat.get('subchannels', []):
            subchannel, child_messages = self._get_all_container_messages(
                self.get_chat_subchannel_messages, 'subchannel', instance_uuid,
                child['id'], languages, page_size
            )
            exported_subchannel = {
                'subchannel': subchannel,
                'messages': child_messages,
                'threads': [],
            }
            for thread in subchannel.get('threads', []):
                exported_subchannel['threads'].append(
                    self._get_complete_thread(
                        instance_uuid, thread['id'], languages, page_size
                    )
                )
            result['subchannels'].append(exported_subchannel)

        for thread in chat.get('threads', []):
            result['threads'].append(
                self._get_complete_thread(
                    instance_uuid, thread['id'], languages, page_size
                )
            )
        return result

    def export_chat(self, instance_uuid, id, output_directory,
                    languages=None, page_size=500):
        """Export one complete chat to a JSON file.

        The filename is derived from a filesystem-safe form of the original
        chat ID and always ends in ``.json``. An existing file with that name is
        replaced after the new export has been written successfully. The chat's
        original, unsanitized ID remains present in its metadata.

        :param instance_uuid: UUID of the chat instance.
        :type instance_uuid: str
        :param id: Original, unsanitized chat identifier returned by AIL.
        :type id: str
        :param output_directory: Directory in which to create the chat file.
        :type output_directory: str or pathlib.Path
        :param languages: Optional comma-separated language string or sequence
            of BCP 47 tags. Values are forwarded unchanged to AIL.
        :type languages: str or sequence or None
        :param page_size: Maximum number of messages requested for each page.
        :type page_size: int
        :return: Path of the created chat JSON file.
        :rtype: pathlib.Path
        :raises AILServerError: If AIL rejects a request during export.
        :raises PyAILUnexpectedResponse: If AIL returns an invalid chat payload.
        """
        directory = Path(output_directory)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / self._chat_export_filename(id)
        chat = self.get_chat_content(
            instance_uuid, id, languages=languages, page_size=page_size
        )

        temporary = self._temporary_file(destination)
        try:
            self._write_json(temporary, chat)
            self._replace_export_path(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        return destination

    def export_chat_instance(self, instance_uuid, output_directory,
                             languages=None, page_size=500,
                             discovery_page_size=50):
        """Export every chat belonging to a chat instance.

        The method creates ``<output_directory>/<sanitized-instance-uuid>/``.
        That directory contains ``metadata.json`` and a ``chats`` directory
        with one complete JSON document per chat. ``metadata.json`` records the
        original chat IDs and their generated filenames. An existing instance
        export is replaced only after the new export completes successfully.

        :param instance_uuid: UUID of the chat instance to export.
        :type instance_uuid: str
        :param output_directory: Parent directory for the instance export.
        :type output_directory: str or pathlib.Path
        :param languages: Optional comma-separated language string or sequence
            of BCP 47 tags. The same value is forwarded unchanged to discovery
            and every message request.
        :type languages: str or sequence or None
        :param page_size: Maximum number of messages requested per page for
            each chat container.
        :type page_size: int
        :param discovery_page_size: Maximum number of chats requested per
            instance-discovery page.
        :type discovery_page_size: int
        :return: Path of the created instance export directory.
        :rtype: pathlib.Path
        :raises AILServerError: If AIL rejects a request during export.
        :raises PyAILUnexpectedResponse: If AIL returns an invalid chat payload.
        """
        export_root = Path(output_directory)
        export_root.mkdir(parents=True, exist_ok=True)
        destination = export_root / self._sanitize_export_name(
            instance_uuid, fallback='instance'
        )
        staging = Path(tempfile.mkdtemp(
            prefix=f'.{destination.name}.', dir=str(export_root)
        ))
        try:
            chats, instance = self._get_all_chats(
                instance_uuid, languages, discovery_page_size
            )
            chats_directory = staging / 'chats'
            chats_directory.mkdir()
            mapping = []
            filenames = {}
            for chat in chats:
                chat_id = chat['id']
                filename = self._chat_export_filename(chat_id)
                if filename in filenames and filenames[filename] != chat_id:
                    stem = filename[:-5]
                    filename = f'{stem}-{uuid4()}.json'
                    while filename in filenames:
                        filename = f'{stem}-{uuid4()}.json'
                filenames[filename] = chat_id
                complete_chat = self.get_chat_content(
                    instance_uuid, chat_id, languages=languages,
                    page_size=page_size
                )
                self._write_json(chats_directory / filename, complete_chat)
                mapping.append({'id': chat_id, 'filename': f'chats/{filename}'})

            metadata = {
                'instance': instance,
                'options': {
                    'languages': languages,
                    'page_size': page_size,
                    'discovery_page_size': discovery_page_size,
                },
                'chats': mapping,
            }
            self._write_json(staging / 'metadata.json', metadata)
            self._replace_export_path(staging, destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return destination

    def _get_complete_thread(self, instance_uuid, thread_id, languages,
                             page_size):
        thread, messages = self._get_all_container_messages(
            self.get_chat_thread_messages, 'thread', instance_uuid, thread_id,
            languages, page_size
        )
        return {'thread': thread, 'messages': messages}

    def _get_all_container_messages(self, method, metadata_key, instance_uuid,
                                    container_id, languages, page_size):
        first = method(
            instance_uuid, container_id, languages=languages,
            page=1, page_size=page_size
        )
        metadata, messages, page_count = self._parse_chat_page(
            first, metadata_key
        )
        for page in range(2, page_count + 1):
            response = method(
                instance_uuid, container_id, languages=languages,
                page=page, page_size=page_size
            )
            _, page_messages, _ = self._parse_chat_page(
                response, metadata_key
            )
            self._append_messages(messages, page_messages)
        return metadata, messages

    def _get_all_chats(self, instance_uuid, languages, page_size):
        response = self.get_chats(
            instance_uuid, languages=languages, page=1, page_size=page_size
        )
        self._raise_chat_api_error(response)
        try:
            instance = response['instance']
            chats = list(response['chats'])
            page_count = int(response['pagination']['page_count'])
        except (KeyError, TypeError, ValueError) as error:
            raise PyAILUnexpectedResponse(
                'Invalid chat discovery response.'
            ) from error
        for page in range(2, page_count + 1):
            response = self.get_chats(
                instance_uuid, languages=languages, page=page,
                page_size=page_size
            )
            self._raise_chat_api_error(response)
            try:
                chats.extend(response['chats'])
            except (KeyError, TypeError) as error:
                raise PyAILUnexpectedResponse(
                    'Invalid chat discovery response.'
                ) from error
        return chats, instance

    @classmethod
    def _parse_chat_page(cls, response, metadata_key):
        cls._raise_chat_api_error(response)
        try:
            metadata = response[metadata_key]
            messages = {
                date_key: list(values)
                for date_key, values in response['messages'].items()
            }
            page_count = int(response['pagination']['page_count'])
        except (KeyError, TypeError, ValueError) as error:
            raise PyAILUnexpectedResponse(
                f'Invalid {metadata_key} message response.'
            ) from error
        return metadata, messages, page_count

    @staticmethod
    def _raise_chat_api_error(response):
        if isinstance(response, dict) and 'errors' in response:
            raise AILServerError(f'Chat API request failed: {response["errors"]}')
        if not isinstance(response, dict):
            raise PyAILUnexpectedResponse('Invalid chat API response.')

    @staticmethod
    def _append_messages(messages, page_messages):
        for date_key, values in page_messages.items():
            messages.setdefault(date_key, []).extend(values)

    @staticmethod
    def _chat_export_filename(chat_id):
        return f'{PyAIL._sanitize_export_name(chat_id, fallback="chat")}.json'

    @staticmethod
    def _sanitize_export_name(value, fallback):
        normalized = unicodedata.normalize('NFKC', str(value))
        base = re.sub(r'[^A-Za-z0-9._-]+', '_', normalized)
        return base.strip('._-')[:120] or fallback

    @staticmethod
    def _temporary_file(destination):
        descriptor, filename = tempfile.mkstemp(
            prefix=f'.{destination.name}.', dir=str(destination.parent)
        )
        os.close(descriptor)
        return Path(filename)

    @staticmethod
    def _write_json(path, value):
        with path.open('w', encoding='utf-8') as export_file:
            json.dump(
                value, export_file, default=ail_json_default,
                ensure_ascii=False, indent=2, sort_keys=True
            )
            export_file.write('\n')

    @staticmethod
    def _replace_export_path(staging, destination):
        if not destination.exists():
            os.replace(str(staging), str(destination))
            return

        backup = destination.with_name(
            f'.{destination.name}.backup-{os.getpid()}-{time.time_ns()}'
        )
        os.replace(str(destination), str(backup))
        try:
            os.replace(str(staging), str(destination))
        except Exception:
            os.replace(str(backup), str(destination))
            raise
        if backup.is_dir():
            shutil.rmtree(backup)
        else:
            backup.unlink()

    ## -- Chats -- ##

    ## -- AIL Server -- ##

    #### AIL Object ####  # TODO get meta/object fields description

    # def exists_object(self, object_type, object_subtype, object_id):
    #     pass
    #
    # def get_object(self, object_type, object_subtype, object_id):
    #     pass

    ## -- AIL Object -- ##

    #### AIL Object ####

    ## -- Investigation -- ##
    #
    # def get_investigations(self):
    #     pass
    #
    # def get_investigation(self, investigation_uuid):
    #     pass

    ## BEGIN Feed AIL ##
    def feed_json_item(self, data, meta, source, source_uuid, data_sha256=None, default_encoding='UTF-8'):
        dict_to_send = {}
        dict_to_send['data'] = encode_and_compress_data(data)
        if data_sha256:
            dict_to_send['data-sha256'] = data_sha256
        else:
            dict_to_send['data-sha256'] = get_data_sha256(data)
        dict_to_send['meta'] = meta
        dict_to_send['source'] = source
        dict_to_send['source_uuid'] = source_uuid
        dict_to_send['default_encoding'] = default_encoding
        dict_to_send['timestamp'] = int(time.time())
        response = self._prepare_request('POST', f'api/{self.api_version}/import/json/item', data=dict_to_send)
        return self._check_json_response(response)

    # feed json file  -------------------

    # # TODO: return task uuid + add check status
    # Crawler #
    def crawl_url(self, url, har=True, screenshot=True, depth_limit=1, frequency=None, cookiejar=None, proxy='force_tor'):
        dict_to_send = {}
        dict_to_send['url'] = url
        dict_to_send['har'] = har
        dict_to_send['screenshot'] = screenshot
        dict_to_send['depth_limit'] = int(depth_limit)
        if cookiejar:
            dict_to_send['cookiejar'] = cookiejar
        # can be set to 'web', 'onion', 'tor' or 'force_tor'
        if proxy:
            dict_to_send['proxy'] = proxy
        # 'monthly', 'weekly', 'daily', 'hourly' or a dict {'minutes': 0, 'hours':0, 'days': 0, 'weeks': 0, 'months': 0}
        if frequency:
            dict_to_send['frequency'] = frequency
        response = self._prepare_request('POST', f'api/{self.api_version}/add/crawler/task', data=dict_to_send)
        return self._check_json_response(response)

    def add_crawler_capture(self, task_uuid, capture_uuid, url, har=False, screenshot=False, depth_limit=1, proxy='force_tor'):
        dict_to_send = {}
        dict_to_send['task_uuid'] = task_uuid
        dict_to_send['capture_uuid'] = capture_uuid
        dict_to_send['url'] = url
        dict_to_send['har'] = har
        dict_to_send['screenshot'] = screenshot
        dict_to_send['depth_limit'] = int(depth_limit)
        # can be set to 'web', 'onion', 'tor' or 'force_tor'
        if proxy:
            dict_to_send['proxy'] = proxy
        response = self._prepare_request('POST', f'api/{self.api_version}/add/crawler/capture', data=dict_to_send)
        return self._check_json_response(response)

    def import_crawler_capture(self, capture=None, capture_file=None):
        """
        Import a crawler capture in Lacus format.

        The Lacus crawler capture is expected to follow the structure:

        {
            "html": <str>,                        # Raw HTML content of the page

            "last_redirected_url": <str>,         # Final resolved URL

            "png": <str | null>,                  # Optional - Base64-encoded screenshot

            "har": <dict | null>,                 # Optional - HAR capture as JSON/dict

            "potential_favicons": <list[str]>,    # Optional - List of base64-encoded icons

            "children": <list[dict]>              # Optional - Recursively embedded captures

        }

        One of the following must be provided:
          • ``capture``: A dictionary in Lacus format.
          • ``capture_file``: Path to a JSON file containing a Lacus capture.

        If ``capture_file`` is provided and ``capture`` is not,
        the file will be read and the parsed JSON used as the capture payload.

        :param capture: (dict) A Lacus-format capture structure.
        :type capture: dict | None
        :param capture_file: (str) Path to a JSON capture file.
        :type capture_file: str | None

        :return: A dict containing the UUID of the imported capture. {"uuid": "<UUID>"}
        :rtype: dict
        """
        if capture_file and not capture:
            with open(capture_file, 'r') as f:
                capture = f.read()
        if not capture:
            raise Exception('capture_file or capture must be provided')
        response = self._prepare_request('POST', f'api/{self.api_version}/import/crawler/capture', data=capture)
        return self._check_json_response(response)

    def import_lacus_cookiejar(self, url, storage):
        dict_to_send = {}
        dict_to_send['url'] = url
        dict_to_send['storage'] = storage
        response = self._prepare_request('POST', f'api/{self.api_version}/lacus/cookiejar/import', data=dict_to_send)
        return self._check_json_response(response)

    def get_crawler_default_user_agent(self):
        response = self._prepare_request('GET', f'api/{self.api_version}/crawler/user-agent/default')
        return self._check_json_response(response)

    def forum_account_login(self, forum_id, account_id, local_storage):
        dict_to_send = {}
        dict_to_send['forum_id'] = forum_id
        dict_to_send['account_id'] = account_id
        dict_to_send['local_storage'] = local_storage
        response = self._prepare_request('POST', f'api/{self.api_version}/forum/crawler/account/login', data=dict_to_send)
        return self._check_json_response(response)

    def onion_lookup(self, onion):
        response = self._prepare_request('GET', f'api/{self.api_version}/lookup/onion/{onion}')
        return self._check_json_response(response)

    ## -- END Feed AIL -- ##

    #### ADMIN ####

    def create_user(self, org_uuid, user_id, role, password=None, otp=True, send_email=True):
        dict_to_send = {'org_uuid': org_uuid, 'id': user_id, 'role': role, 'otp': otp, 'send_email': send_email}
        if password:
            dict_to_send['password'] = password
        response = self._prepare_request('POST', f'api/{self.api_version}/user/create', data=dict_to_send)
        return self._check_json_response(response)

    ## -- ADMIN -- ##

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

    #################################################################################
    #################################################################################
    #################################################################################

    # AIL OBJECTS for a tpe ????

    #################################################################################
    #################################################################################
    #################################################################################

    # add_tag(ref_obj, tag)

    # add_investigation / create_investigation
    # add_tracker / create_tracker

    # add_object / create_object -> accept AILObject + dict/json -> type or var like pythonify

    # direct_call but a with better name
