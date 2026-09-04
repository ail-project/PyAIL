# -*- coding: utf-8 -*-

import base64
import gzip
import json
import re
import unicodedata

from datetime import date, datetime
from enum import Enum
from hashlib import sha256
from uuid import UUID

# # TODO: add exception
def encode_and_compress_data(data):
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
    return base64.b64encode(gzip.compress(data)).decode()

# # TODO: add exception
# # TODO: add encoding
def get_data_sha256(data):
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
    m = sha256()
    m.update(data)
    return m.hexdigest()

# # TODO: ADD NEW AIL OBJECT
def ail_json_default(obj):
    # datetime
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    # ENUM
    elif isinstance(obj, Enum):
        return obj.value
    # UUID
    elif isinstance(obj, UUID):
        return str(obj)


def sanitize_export_name(value, fallback):
    normalized = unicodedata.normalize('NFKC', str(value))
    base = re.sub(r'[^A-Za-z0-9._-]+', '_', normalized)
    return base.strip('._-')[:120] or fallback


def write_json(path, value):
    with path.open('w', encoding='utf-8') as export_file:
        json.dump(value, export_file, default=ail_json_default, ensure_ascii=False)
        export_file.write('\n')


def dump_json_value(export_file, value):
    json.dump(value, export_file, default=ail_json_default, ensure_ascii=False)
