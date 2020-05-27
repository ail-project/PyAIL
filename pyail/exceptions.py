# -*- coding: utf-8 -*-


class PyAILError(Exception):
    def __init__(self, message):
        super(PyAILError, self).__init__(message)
        self.message = message


class MissingDependency(PyAILError):
    pass


class NoURL(PyAILError):
    pass


class NoKey(PyAILError):
    pass


class PyAILInvalidFormat(PyAILError):
    pass


class AILServerError(PyAILError):
    pass


class PyAILNotImplementedYet(PyAILError):
    pass


class PyAILUnexpectedResponse(PyAILError):
    pass


class PyAILEmptyResponse(PyAILError):
    pass
