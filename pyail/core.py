# -*- coding: utf-8 -*-

import base64
import gzip
from hashlib import sha256

# # TODO: add exception
def encode_and_compress_data(data):
    return base64.b64encode(gzip.compress(data.encode('utf-8'))).decode()

# # TODO: add exception
# # TODO: add encoding
def get_data_sha256(data):
    m = sha256()
    m.update(data.encode('utf-8'))
    return m.hexdigest()
