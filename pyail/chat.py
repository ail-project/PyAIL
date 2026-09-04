# -*- coding: utf-8 -*-

from .core import sanitize_export_name
from .exceptions import AILServerError, PyAILUnexpectedResponse


def chat_query_params(page, page_size, languages=None, **params):
    params.update({'page': page, 'page_size': page_size})
    if languages is not None:
        params['languages'] = languages
    return params


def raise_chat_api_error(response):
    if isinstance(response, dict) and 'errors' in response:
        raise AILServerError(f'Chat API request failed: {response["errors"]}')
    if not isinstance(response, dict):
        raise PyAILUnexpectedResponse('Invalid chat API response.')


def parse_chat_discovery_page(response):
    raise_chat_api_error(response)
    try:
        instance = response['instance']
        chats = list(response['chats'])
        page_count = int(response['pagination']['page_count'])
    except (KeyError, TypeError, ValueError) as error:
        raise PyAILUnexpectedResponse(
            'Invalid chat discovery response.'
        ) from error
    return instance, chats, page_count


def parse_chat_page(response, metadata_key):
    raise_chat_api_error(response)
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


def append_messages(messages, page_messages):
    for date_key, values in page_messages.items():
        messages.setdefault(date_key, []).extend(values)


def chat_export_filename(chat_id):
    return f'{sanitize_export_name(chat_id, fallback="chat")}.json'


def languages_for_json(languages):
    if languages is None or isinstance(languages, str):
        return languages
    return list(languages)
