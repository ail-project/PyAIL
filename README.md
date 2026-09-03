PyAIL
======

[![Python 3.6](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/release/python-360/)

# PyAIL - Python library using the AIL Rest API

PyAIL is a Python library to access [AIL](https://github.com/ail-project/ail-framework) platforms via their REST API.

## Install from pip

**It is strongly recommended to use a virtual environment**

If you want to know more about virtual environments, [python has you covered](https://docs.python.org/3/tutorial/venv.html)

Install pyail:
```bash
pip3 install pyail
```

## Usage

### Creating an AIL client

```python
from pyail import PyAIL

ail_url = 'https://localhost:7000'
ail_key = '<AIL API KEY>'
try:
    pyail = PyAIL(ail_url, ail_key, ssl=False)
except Exception as e:
    print(e)
    sys.exit(0)

pyail.ping()
```

### Feeding items to AIL

```python
data = 'my item content'
metadata = {}
source = '<FEEDER NAME>'
source_uuid = '<feeder UUID v4>'

pyail.feed_json_item(data, metadata, source, source_uuid)
```
### Import Crawler capture

```python
pyail.import_crawler_capture(capture={"last_redirected_url": "https://mywebsite.com", "html": "<html><body><h1>HELLO WORLD</h1></body></html>"})
```

### Discovering chats and downloading messages

Chat instance and chat listings are paginated. Language filters can be passed
as either a comma-separated string or a list:

```python
instances = pyail.get_chat_instances(page=1, page_size=50)
chats = pyail.get_chats(
    instances['instances'][0]['uuid'],
    languages=['en', 'fr'],
)
```

Messages are paginated independently for each chat container. Child metadata
in a chat or subchannel response provides the original IDs to pass to the
corresponding method:

```python
instance_uuid = instances['instances'][0]['uuid']
chat_id = chats['chats'][0]['id']

chat_page = pyail.get_chat_messages(instance_uuid, chat_id)
subchannel = chat_page['chat']['subchannels'][0]
subchannel_page = pyail.get_chat_subchannel_messages(
    instance_uuid,
    subchannel['id'],
)

thread = subchannel_page['subchannel']['threads'][0]
thread_page = pyail.get_chat_thread_messages(instance_uuid, thread['id'])
```

Use `get_chat_content` to assemble all independently paginated containers in
memory. Complete chats can also be written directly as JSON:

```python
complete_chat = pyail.get_chat_content(
    instance_uuid,
    chat_id,
    languages=['en', 'fr'],
)
pyail.export_chat(
    instance_uuid,
    chat_id,
    'exports',
    languages=['en', 'fr'],
)
```

An entire instance is exported as one metadata file and one JSON file per chat:

```python
pyail.export_chat_instance(
    instance_uuid,
    'exports',
    languages=['en', 'fr'],
)
```

Exports overwrite existing destinations. Single-chat exports use the sanitized
chat ID as their filename, while instance exports create a sanitized instance
UUID directory. Filename collisions receive a UUIDv4 suffix, and each original
chat ID remains in both the mapping and chat metadata. See
[`docs/chat-export-design.md`](docs/chat-export-design.md) for the complete
format and failure behavior.

# License


This software is licensed under BSD 3-Clause License

Copyright (C) 2020-2025 CIRCL - Computer Incident Response Center Luxembourg

Copyright (C) 2020-2025 Aurelien Thirion
