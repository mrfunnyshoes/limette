"""Low level wrapper for connecting to the LSRC2."""
from typing import Any, NamedTuple

import requests

from citric.exceptions import (
    LimeSurveyApiError,
    LimeSurveyError,
    LimeSurveyStatusError,
)


class RPCResponse(NamedTuple):
    """LimeSurvey RPC response object.

    :param result: RPC result.
    :param error: Error message, if any.
    :param id: RPC Request ID.
    """

    result: Any
    error: Any
    id: Any

    @classmethod
    def parse_response(cls, response):
        """Parse a requests response into an RPC response.

        A exception is raised when LimeSurvey responds with an empty message,
        an explicit error, or a bad status.
        """

        if response.text == "":
            raise LimeSurveyError("RPC interface not enabled")

        json_data = response.json()
        rpc = cls(**json_data)

        if isinstance(rpc.result, dict) and rpc.result.get("status") is not None:
            raise LimeSurveyStatusError(rpc)

        if rpc.error is not None:
            raise LimeSurveyApiError(rpc)

        return rpc


class BaseRPC:
    """Base class for executing RPC in the LimeSurvey."""

    def invoke(self):
        raise NotImplementedError


class JSONRPC(BaseRPC):
    """Execute JSON-RPC in LimeSurvey."""

    _headers = {
        "content-type": "application/json",
        "user-agent": "citric-client",
    }

    def __init__(self):
        self.request_session = requests.Session()
        self.request_session.headers.update(self._headers)

    def invoke(self, url, method, *args, request_id=1):

        payload = {
            "method": method,
            "params": [*args],
            "id": request_id,
        }

        res = self.request_session.post(url, json=payload)

        response = RPCResponse.parse_response(res)

        return response


class Session(object):
    """LimeSurvey RemoteControl 2 API session.

    :param url: LimeSurvey Remote Control endpoint.
    :type url: ``str``
    :param admin_user: LimeSurvey user name.
    :type admin_user: ``str``
    :param admin_pass: LimeSurvey password.
    :type admin_pass: ``str``
    :param spec: RPC specification
    :type spec: ``BaseRPC``
    """

    __attrs__ = ["url", "key"]

    def __init__(self, url, admin_user, admin_pass, spec=JSONRPC()):
        """Create LimeSurvey wrapper."""
        self.url = url
        self.spec = spec
        self.key = self.get_session_key(admin_user, admin_pass)

    def rpc(self, method, *args, request_id=1):
        r"""Authenticated execution of an RPC method on LimeSurvey.

        :param method: Name of the method to call.
        :type method: ``str``
        :param \*args: Postional arguments of the RPC method.
        :type \*args: ``Any``
        :param request_id: Request ID for response validation.
        :type request_id: ``int``
        """
        return self.spec.invoke(
            self.url, method, self.key, *args, request_id=request_id,
        )

    def get_session_key(self, admin_user, admin_pass, request_id=1):
        """Get RC API session key.

        :param admin_user: LimeSurvey admin username.
        :type admin_user: ``str``
        :param admin_pass: LimeSurvey admin password.
        :type admin_pass: ``str``
        :param request_id: LimeSurvey RPC request ID.
        :type request_id: ``Any``
        """

        response = self.spec.invoke(
            self.url, "get_session_key", admin_user, admin_pass, request_id=request_id,
        )

        return response.result

    def close(self):
        """Close RC API session."""
        self.rpc("release_session_key")

    def __enter__(self):
        """Context manager for API session."""
        return self

    def __exit__(self, type, value, traceback):
        """Safely exit an API session."""
        self.close()