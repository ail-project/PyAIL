__version__ = '0.0.2'
import logging

FORMAT = "%(levelname)s [%(filename)s:%(lineno)s - %(funcName)s() ] %(message)s"
formatter = logging.Formatter(FORMAT)
default_handler = logging.StreamHandler()
default_handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.addHandler(default_handler)
logger.setLevel(logging.WARNING)


everything_broken = '''Unknown error: the response is not in JSON.
Something is broken server-side, please send us everything that follows (careful with the auth key):
Request headers:
{}
Request body:
{}
Response (if any):
{}'''


try:
    from .exceptions import PyAILError, MissingDependency, NoURL, NoKey, PyAILInvalidFormat, AILServerError, PyAILNotImplementedYet, PyAILUnexpectedResponse, PyAILEmptyResponse
    from .api import PyAIL
    logger.debug('pyail loaded properly')
except ImportError as e:
    logger.warning('Unable to load pyail properly: {}'.format(e))
