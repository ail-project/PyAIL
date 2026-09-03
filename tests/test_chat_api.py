from unittest.mock import Mock
import json
import inspect

import pytest

from pyail.api import PyAIL
from pyail.exceptions import AILServerError


@pytest.fixture
def client():
    client = PyAIL.__new__(PyAIL)
    client.api_version = 'v1'
    client._prepare_request = Mock(return_value=Mock())
    client._check_json_response = Mock(return_value={'ok': True})
    return client


def assert_get(client, path, params):
    response = client._prepare_request.return_value
    client._prepare_request.assert_called_once_with('GET', path, params=params)
    client._check_json_response.assert_called_once_with(response)


def test_get_chat_instances(client):
    assert client.get_chat_instances(page=2, page_size=25) == {'ok': True}

    assert_get(client, 'api/v1/chat/instances', {
        'page': 2,
        'page_size': 25,
    })


@pytest.mark.parametrize('languages', ['en,fr', ['en', 'fr']])
def test_get_chats_accepts_both_language_filter_forms(client, languages):
    assert client.get_chats(
        'instance-uuid', languages=languages, page=3, page_size=10
    ) == {'ok': True}

    assert_get(client, 'api/v1/chat/instances/instance-uuid/chats', {
        'languages': languages,
        'page': 3,
        'page_size': 10,
    })


@pytest.mark.parametrize(('method_name', 'container_id', 'path'), [
    ('get_chat_messages', 'chat/with/slashes', 'api/v1/chat/messages'),
    (
        'get_chat_subchannel_messages',
        'chat/with/slashes/general',
        'api/v1/chat/subchannel/messages',
    ),
    (
        'get_chat_thread_messages',
        'chat/with/slashes/thread-1',
        'api/v1/chat/thread/messages',
    ),
])
def test_get_container_messages_keeps_id_in_query_parameters(
        client, method_name, container_id, path):
    method = getattr(client, method_name)

    assert method(
        'instance-uuid', container_id, languages=['en', 'fr'],
        page=4, page_size=100
    ) == {'ok': True}

    assert_get(client, path, {
        'instance_uuid': 'instance-uuid',
        'id': container_id,
        'languages': ['en', 'fr'],
        'page': 4,
        'page_size': 100,
    })


def test_optional_language_filter_is_omitted(client):
    client.get_chat_messages('instance-uuid', 'chat-id')

    assert_get(client, 'api/v1/chat/messages', {
        'instance_uuid': 'instance-uuid',
        'id': 'chat-id',
        'page': 1,
        'page_size': 500,
    })


@pytest.mark.parametrize('method_name', [
    'get_chat_messages',
    'get_chat_subchannel_messages',
    'get_chat_thread_messages',
    'get_chat_content',
    'export_chat',
])
def test_chat_container_public_methods_use_generic_id_parameter(method_name):
    parameters = inspect.signature(getattr(PyAIL, method_name)).parameters

    assert 'id' in parameters
    assert 'chat_id' not in parameters
    assert 'subchannel_id' not in parameters
    assert 'thread_id' not in parameters


def message_page(kind, metadata, page, page_count, messages):
    return {
        kind: metadata,
        'messages': messages,
        'pagination': {
            'page': page,
            'page_size': 1,
            'page_count': page_count,
            'total': page_count,
        },
    }


def test_complete_chat_fetches_every_container_page_and_hierarchy():
    client = PyAIL.__new__(PyAIL)
    languages = ['en', 'fr']
    calls = []
    chat = {
        'id': 'chat/id',
        'subchannels': [{'id': 'sub/id'}],
        'threads': [{'id': 'direct/thread'}],
    }
    subchannel = {
        'id': 'sub/id',
        'threads': [{'id': 'sub/thread'}],
    }

    def paged(kind, metadata, prefix):
        def request(instance_uuid, container_id, **params):
            calls.append((kind, instance_uuid, container_id, params))
            page = params['page']
            return message_page(
                kind, metadata, page, 2,
                {'2024/01/01': [f'{prefix}-{page}']},
            )
        return request

    client.get_chat_messages = paged('chat', chat, 'chat')
    client.get_chat_subchannel_messages = paged(
        'subchannel', subchannel, 'subchannel'
    )

    def threads(instance_uuid, container_id, **params):
        calls.append(('thread', instance_uuid, container_id, params))
        page = params['page']
        return message_page(
            'thread', {'id': container_id}, page, 2,
            {'2024/01/01': [f'{container_id}-{page}']},
        )

    client.get_chat_thread_messages = threads
    result = client.get_chat_content(
        'instance', 'chat/id', languages=languages, page_size=1
    )

    assert result['messages']['2024/01/01'] == ['chat-1', 'chat-2']
    assert result['subchannels'][0]['messages']['2024/01/01'] == [
        'subchannel-1', 'subchannel-2'
    ]
    assert result['threads'][0]['thread']['id'] == 'direct/thread'
    assert result['subchannels'][0]['threads'][0]['thread']['id'] == 'sub/thread'
    assert len(calls) == 8
    assert all(call[3]['languages'] is languages for call in calls)
    assert all(call[3]['page_size'] == 1 for call in calls)


def test_complete_empty_chat():
    client = PyAIL.__new__(PyAIL)
    client.get_chat_messages = Mock(return_value=message_page(
        'chat', {'id': 'empty', 'subchannels': [], 'threads': []},
        1, 0, {}
    ))
    client.get_chat_subchannel_messages = Mock()
    client.get_chat_thread_messages = Mock()

    result = client.get_chat_content('instance', 'empty')

    assert result == {
        'chat': {'id': 'empty', 'subchannels': [], 'threads': []},
        'messages': {},
        'subchannels': [],
        'threads': [],
    }
    client.get_chat_subchannel_messages.assert_not_called()
    client.get_chat_thread_messages.assert_not_called()


def discovery_page(instance, chats, page=1, page_count=1):
    return {
        'instance': instance,
        'chats': chats,
        'pagination': {
            'page': page,
            'page_size': 50,
            'page_count': page_count,
            'total': len(chats),
        },
    }


def complete_chat(chat_id):
    return {
        'chat': {'id': chat_id},
        'messages': {},
        'subchannels': [],
        'threads': [],
    }


def test_instance_export_handles_empty_instance(tmp_path):
    client = PyAIL.__new__(PyAIL)
    instance = {'uuid': 'instance', 'chat_count': 0}
    client.get_chats = Mock(return_value=discovery_page(instance, []))
    client.get_chat_content = Mock()

    output = client.export_chat_instance('instance', tmp_path / 'export')

    metadata = json.loads((output / 'metadata.json').read_text())
    assert metadata['instance'] == instance
    assert metadata['chats'] == []
    assert list((output / 'chats').iterdir()) == []
    client.get_chat_content.assert_not_called()


def test_instance_export_uses_safe_collision_resistant_names(tmp_path):
    client = PyAIL.__new__(PyAIL)
    ids = ['../../same/name', '..\\..\\same/name', 'same:name']
    instance = {'uuid': 'instance'}
    client.get_chats = Mock(return_value=discovery_page(
        instance, [{'id': chat_id} for chat_id in ids]
    ))
    client.get_chat_content = Mock(side_effect=lambda _, chat_id, **kwargs:
                                    complete_chat(chat_id))

    first = client.export_chat_instance('instance', tmp_path / 'first')
    first_metadata = json.loads((first / 'metadata.json').read_text())

    first_mapping = first_metadata['chats']
    assert len({entry['filename'] for entry in first_mapping}) == len(ids)
    for original, entry in zip(ids, first_mapping):
        assert entry['id'] == original
        filename = entry['filename']
        assert filename.startswith('chats/') and filename.endswith('.json')
        exported_path = first / filename
        assert first.resolve() in exported_path.resolve().parents
        assert json.loads(exported_path.read_text())['chat']['id'] == original


def test_sanitization_produces_the_chat_id_filename():
    first = PyAIL._chat_export_filename('same/name')
    second = PyAIL._chat_export_filename('same:name')

    assert first == 'same_name.json'
    assert second == 'same_name.json'


def test_collision_appends_uuid4_and_records_final_mapping(tmp_path):
    client = PyAIL.__new__(PyAIL)
    client.get_chats = Mock(return_value=discovery_page(
        {'uuid': 'instance'}, [{'id': 'same/name'}, {'id': 'same:name'}]
    ))
    client.get_chat_content = Mock(
        side_effect=lambda _, chat_id, **kwargs: complete_chat(chat_id)
    )

    output = client.export_chat_instance('instance', tmp_path)
    mapping = json.loads((output / 'metadata.json').read_text())['chats']

    assert mapping[0] == {'id': 'same/name', 'filename': 'chats/same_name.json'}
    collision = mapping[1]['filename']
    assert mapping[1]['id'] == 'same:name'
    assert collision.startswith('chats/same_name-')
    assert collision.endswith('.json')
    uuid = collision[len('chats/same_name-'):-len('.json')]
    assert len(uuid) == 36 and uuid[14] == '4'


def test_instance_export_propagates_language_filter_to_discovery_and_chats(
        tmp_path):
    client = PyAIL.__new__(PyAIL)
    languages = 'en,fr'
    client.get_chats = Mock(return_value=discovery_page(
        {'uuid': 'instance'}, [{'id': 'one'}]
    ))
    client.get_chat_content = Mock(return_value=complete_chat('one'))

    client.export_chat_instance(
        'instance', tmp_path / 'export', languages=languages,
        page_size=123, discovery_page_size=12
    )

    client.get_chats.assert_called_once_with(
        'instance', languages=languages, page=1, page_size=12
    )
    client.get_chat_content.assert_called_once_with(
        'instance', 'one', languages=languages, page_size=123
    )


def test_instance_discovery_fetches_all_pages(tmp_path):
    client = PyAIL.__new__(PyAIL)
    instance = {'uuid': 'instance'}
    client.get_chats = Mock(side_effect=[
        discovery_page(instance, [{'id': 'one'}], page=1, page_count=2),
        discovery_page(instance, [{'id': 'two'}], page=2, page_count=2),
    ])
    client.get_chat_content = Mock(
        side_effect=lambda _, chat_id, **kwargs: complete_chat(chat_id)
    )

    output = client.export_chat_instance('instance', tmp_path / 'export')

    metadata = json.loads((output / 'metadata.json').read_text())
    assert [entry['id'] for entry in metadata['chats']] == ['one', 'two']
    assert [call.kwargs['page'] for call in client.get_chats.call_args_list] == [1, 2]


def test_api_failure_during_instance_export_leaves_no_partial_output(tmp_path):
    client = PyAIL.__new__(PyAIL)
    client.get_chats = Mock(return_value=discovery_page(
        {'uuid': 'instance'}, [{'id': 'one'}, {'id': 'two'}]
    ))
    client.get_chat_content = Mock(side_effect=[
        complete_chat('one'),
        AILServerError('page failed'),
    ])
    destination = tmp_path / 'export'

    with pytest.raises(AILServerError, match='page failed'):
        client.export_chat_instance('instance', destination)

    assert destination.exists()
    assert list(destination.iterdir()) == []


def test_api_failure_during_multi_page_chat_is_raised():
    client = PyAIL.__new__(PyAIL)
    client.get_chat_messages = Mock(side_effect=[
        message_page('chat', {'id': 'one'}, 1, 2, {}),
        {'errors': (500, {'reason': 'failed'})},
    ])

    with pytest.raises(AILServerError, match='Chat API request failed'):
        client.get_chat_content('instance', 'one')


def test_existing_destination_is_overwritten_atomically(tmp_path):
    client = PyAIL.__new__(PyAIL)
    client.get_chats = Mock(return_value=discovery_page(
        {'uuid': 'instance'}, []
    ))
    export_root = tmp_path / 'export'
    destination = export_root / 'instance'
    destination.mkdir(parents=True)
    old = destination / 'old.txt'
    old.write_text('old')

    returned = client.export_chat_instance('instance', export_root)

    assert returned == destination
    assert not old.exists()
    assert (destination / 'metadata.json').exists()


def test_single_chat_export_preserves_existing_file_on_failure(tmp_path):
    client = PyAIL.__new__(PyAIL)
    destination = tmp_path / 'chat.json'
    destination.write_text('old')
    client.get_chat_content = Mock(side_effect=AILServerError('failed'))

    with pytest.raises(AILServerError):
        client.export_chat(
            'instance', 'chat', tmp_path
        )

    assert destination.read_text() == 'old'


def test_single_chat_export_uses_sanitized_id_returns_path_and_overwrites(
        tmp_path):
    client = PyAIL.__new__(PyAIL)
    client.get_chat_content = Mock(return_value=complete_chat('../chat/id'))
    destination = tmp_path / 'chat_id.json'
    destination.write_text('old')

    returned = client.export_chat('instance', '../chat/id', tmp_path)

    assert returned == destination
    assert json.loads(destination.read_text())['chat']['id'] == '../chat/id'


def test_instance_export_uses_sanitized_instance_uuid_as_root(tmp_path):
    client = PyAIL.__new__(PyAIL)
    client.get_chats = Mock(return_value=discovery_page(
        {'uuid': '../unsafe/instance'}, []
    ))

    returned = client.export_chat_instance('../unsafe/instance', tmp_path)

    assert returned == tmp_path / 'unsafe_instance'
    assert returned.parent == tmp_path
