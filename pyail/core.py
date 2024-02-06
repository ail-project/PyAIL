# -*- coding: utf-8 -*-

import base64
import gzip
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
