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

### Feeding items to AIL

```python
from pyail import PyAIL

ail_url = 'https://localhost:7000'
ail_key = '<AIL API KEY>'
try:
    pyail = PyAIL(ail_url, ail_key, ssl=False)
except Exception as e:
    print(e)
    sys.exit(0)

data = 'my item content'
metadata = {}
source = '<FEEDER NAME>'
source_uuid = '<feeder UUID v4>'

pyail.feed_json_item(data, metadata, source, source_uuid)
```


# License


This software is licensed under BSD 3-Clause License

Copyright (C) 2020-2023 CIRCL - Computer Incident Response Center Luxembourg

Copyright (C) 2020-2023 Aurelien Thirion



