"""Provides classes to interact with the Toggl.com REST APIs.

This file is part of toggl-fetch, see https://github.com/Tblue/toggl-fetch.

Copyright 2016  Tilman Blumenbach

toggl-fetch is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

toggl-fetch is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with toggl-fetch.  If not, see http://www.gnu.org/licenses/.
"""

import json
import logging
import time
from abc import *

import requests
import requests.exceptions


# User agent to use for API requests
USER_AGENT = "toggl-fetch (https://github.com/Tblue/toggl-fetch)"

# The logger used by this module
_logger = logging.getLogger(__name__)

# Session cache. See _get_session().
_sessions = {}


def _get_session(auth):
    """Retrieve a possibly cached requests session for the specified Toggl.com user credentials.

    Why not just create a new session object using the same credentials, you ask? Because then, you won't be able
    to make use of connection pooling.

    :param auth: Toggl.com user credentials to use in API requests. Tuple of (username, password) or
        (api_token, "api_token").
    :type auth: (str, str)
    :return: requests session object using the specified credentials.
    :rtype: requests.sessions.Session
    """
    if auth not in _sessions:
        _logger.debug("Creating new session for auth %s", auth)

        _sessions[auth] = requests.Session()
        _sessions[auth].auth = auth

        # Set the user agent, prepending our own agent string to a possibly existing user agent string
        orig_user_agent = _sessions[auth].headers.get("user-agent")
        new_user_agent = USER_AGENT

        if orig_user_agent:
            new_user_agent += " " + orig_user_agent

        _sessions[auth].headers["user-agent"] = new_user_agent
        _sessions[auth].params["user_agent"] = USER_AGENT

        _logger.debug("Final user agent: %s", _sessions[auth].headers["user-agent"])
    else:
        _logger.debug("Reusing existing session for auth %s", auth)

    return _sessions[auth]


class APIError(Exception):
    """Base class for all exceptions explicitly raised by this module. Also raised for general API errors."""
    def __init__(self, message):
        self._message = message

    def __str__(self):
        return self._message


class AuthenticationError(APIError):
    """Raised if invalid user credentials were supplied."""
    pass


class RateLimitingError(APIError):
    """Raised if the API rate limit was exceeded.

    Used internally. If you see this exception when using this module, then that means that we tried to "slow down"
    in order to conform to the rate limiting of 1 req/s, but that didn't work for some reason.
    """
    pass


class _APIBase(metaclass=ABCMeta):
    """Provides basic functionality for Toggl.com API client classes.

    Not intended for direct use. Extend this class to implement a client for a specific Toggl API.
    """
    def __init__(self, api_base_url, api_token):
        """Create a new **generic** Toggl API client.

        Do not call this directly. This constructor is intended to be called by child classes (which implement a
        *specific* Toggl API).

        :param api_base_url: Toggl.com API base URL. Must end with a slash.
        :type api_base_url: str
        :param api_token: API token used for authentication.
        :type api_token: str
        """
        self._api_base_url = api_base_url
        self._session = _get_session((api_token, "api_token"))

    def _do_get(self, path, attempts=3, decode_json=True, **params):
        """Perform a HTTP GET request.

        Please also see the :meth:`_check_error()` method of the extending class for more details on raised exceptions.

        :param path: API "method" to call. This is the HTTP path without the API base URL specified in the constructor.
        :type path: str
        :param attempts: How often the request should be retried if a non-fatal error occurs.
        :type attempts: int
        :param decode_json: Whether to treat the API response as JSON. If ``True``, then the response is decoded as
            JSON and the result (usually a ``dict``) is returned. If ``False``, then the response is non decoded and
            a ``bytes`` object is returned.
        :type decode_json: bool
        :param params: Keyword parameters: Each parameter is added to the query string (and converted to ``str``
            before doing so).
        :type params: dict
        :return: A ``bytes`` object if ``decode_json`` is set to ``False``. Otherwise, the decoded API response
            (treated as JSON) is returned.
        :rtype: object
        :raises requests.exceptions.RequestException: If an HTTP-related error occurs. This is only a base exception,
            the most important more specific exceptions can be found here:
            http://docs.python-requests.org/en/master/user/quickstart/#errors-and-exceptions
        :raises json.decoder.JSONDecodeError: JSON decoding was requested, but the HTTP response payload is not a valid
            JSON document.
        :raises RateLimitingError: API rate limit exceeded.
        """
        for attempt in range(1, attempts + 1):
            try:
                # Perform the GET request
                resp = self._session.get(self._api_base_url + path, params=params)

                # This will throw an exception (caught below) if the response has errors.
                self._check_error(resp)

                if decode_json:
                    return resp.json()

                return resp.content
            except (RateLimitingError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                # NB: We don't catch HTTP errors here (except for "Too many requests") since those should be considered
                #     fatal.
                if attempt == attempts:
                    # Tried and failed <attempts> times, give up.
                    raise

                # Wait 1 sec before retrying
                time.sleep(1)

    @abstractmethod
    def _check_error(self, response):
        """Check a response for errors.

        Should raise an exception if the response has errors and do nothing if the response denotes a success.

        :param response: HTTP response object
        :type response: requests.models.Response
        :return: Nothing.
        :rtype: None
        """
        pass


class Toggl(_APIBase):
    """Provides an API client for the "normal" `Toggl.com API`_, version 8 (e. g. this is **not** a client for the
    `Toggl.com reports API`_; see :class:`.TogglReports` for that).

    .. _Toggl.com API: https://github.com/toggl/toggl_api_docs/blob/master/toggl_api.md
    .. _Toggl.com reports API: https://github.com/toggl/toggl_api_docs/blob/master/reports.md
    """

    # The base URL of the Toggl.com API
    API_BASE_URL = "https://www.toggl.com/api/v8/"

    def __init__(self, api_token):
        """
        Create a new client for the Toggl API, version 8.

        :param api_token: API token to use for authentication.
        :type api_token: str
        """
        super().__init__(self.API_BASE_URL, api_token)

    def _check_error(self, response):
        """
        Check if an HTTP is valid and raise the correct exception if it is not.

        Details on API errors:
          - Rate limiting (error 429): https://github.com/toggl/toggl_api_docs/blob/master/README.md#the-api-format
          - Error 404: https://github.com/toggl/toggl_api_docs/blob/master/toggl_api.md#failed-requests
          - Error 403: https://github.com/toggl/toggl_api_docs/blob/master/toggl_api.md#authentication

        :param response: HTTP response
        :type response: requests.models.Response
        :raises .APIError: If a generic API error occurs. The string representation of the exception will include
            human-readable details about the error.
        :raises .AuthenticationError: Invalid API token supplied.
        :raises .RateLimitingError: API rate limit exceeded.
        :raises requests.exceptions.HTTPError: Unhandled HTTP error occurred.
        """
        if response.status_code == 404:
            # Processing of the API request failed for some reason
            raise APIError("; ".join(response.json()))

        if response.status_code == 403:
            # Authentication failed
            raise AuthenticationError("Invalid API token")

        if response.status_code == 429:
            # Rate limit reached
            raise RateLimitingError("Request limit reached")

        # Raise an exception for all other unsuccessful HTTP status codes we didn't handle above
        response.raise_for_status()

    @staticmethod
    def get_workspace_by_name_from_user_info(user_info, workspace_name):
        """Resolve a workspace name by searching the Toggl.com user information for a workspace with that name.

        Details:
          - List of returned workspace properties:
            https://github.com/toggl/toggl_api_docs/blob/master/chapters/workspaces.md#workspaces

        :param user_info: User information as returned by :meth:`get_user_info`.
        :type user_info: dict
        :param workspace_name: Workspace name to resolve.
        :type workspace_name: str
        :return: ``dict`` describing the resolved workspace or ``None`` if no workspace with the given name
            can be found.
        :rtype: dict | None
        """
        for workspace in user_info["data"]["workspaces"]:
            if workspace["name"] == workspace_name:
                return workspace

        # Not found
        return None

    def get_user_info(self):
        """Get extended user information (for the currently logged in user).

        See :meth:`_do_get` for details on raised exceptions.

        Details:
          - List of returned user properties:
            https://github.com/toggl/toggl_api_docs/blob/master/chapters/users.md#users
          - The returned data also includes "all the workspaces, clients, projects, tasks, time entries and tags
            which the user can see", as described here:
            https://github.com/toggl/toggl_api_docs/blob/master/chapters/users.md#get-current-user-data

        :return: User data, as described above.
        :rtype: dict
        """
        return self._do_get("me", with_related_data="true")


class TogglReports(_APIBase):
    """Provides an API client for the `Toggl.com reports API`_, version 2.

    .. _Toggl.com reports API: https://github.com/toggl/toggl_api_docs/blob/master/reports.md
    """

    # Base URL for the Toggl.com reports API
    API_BASE_URL = "https://www.toggl.com/reports/api/v2/"

    def __init__(self, api_token):
        """
        Create a new client for the Toggl reports API, version 2.

        :param api_token: API token to use for authentication.
        :type api_token: str
        """
        super().__init__(self.API_BASE_URL, api_token)

    def _check_error(self, response, log_warnings=True):
        """
        Check if an HTTP is valid and raise the correct exception if it is not.

        Details on API errors:
          - Rate limiting (error 429): https://github.com/toggl/toggl_api_docs/blob/master/reports.md#rate-limiting
          - Failed requests in general (HTTP codes 400 and up):
            https://github.com/toggl/toggl_api_docs/blob/master/reports.md#failed-requests

        :param response: HTTP response
        :type response: requests.models.Response
        :param log_warnings: If ``True``, then log the contents of ``Warning`` headers in the response with log level
            WARNING.
        :type log_warnings: bool
        :raises .RateLimitingError: API rate limit exceeded.
        :raises requests.exceptions.HTTPError: Unhandled HTTP error occurred.
        :raises .APIError: If a generic API error occurs. The string representation of the exception will include
            human-readable details about the error.
        """
        # Check for "Warning" headers and log their contents (if requested by the caller)
        if log_warnings and "warning" in response.headers:
            original_url = response.request.url
            _logger.warning(
                    "Server warning for URL {} (requested URL: {}): {}".format(
                            response.url, original_url, response.headers["warning"]
                    )
            )

        if response.status_code == 429:
            # Rate limiting triggered
            raise RateLimitingError("Request limit reached")

        if response.status_code < 400:
            # All good.
            return

        # Try to extract an API error message from the response
        try:
            data = response.json()
        except json.JSONDecodeError:
            # Doesn't seem to be a valid API error response (cannot decode JSON). Pretend that the response was valid
            # JSON, but didn't include any error details. This will lead to an exception for the HTTP status code being
            # raised below.
            data = {}

        if "error" not in data:
            # Invalid API response (no error details), just raise an exception for the HTTP status code
            response.raise_for_status()
        else:
            # We have error details, so we can raise a "proper" API error exception
            raise APIError(
                    "Error #{error[code]}: {error[message]} - {error[tip]}".format(error=data["error"])
            )

    def get_summary(self, as_pdf=False, **params):
        """
        Retrieve a summary report for a workspace.

        Please also see the :meth:`_check_error()` method of the extending class for more details on raised
        exceptions.

        :param as_pdf: If ``True``, then a ``bytes`` object containing the report as a PDF document is returned.
            If ``False``, then the report is returned as a ``dict``.
        :type as_pdf: bool
        :param params: See the following resources for a list of valid parameters:

            - https://github.com/toggl/toggl_api_docs/blob/master/reports.md#request-parameters
            - https://github.com/toggl/toggl_api_docs/blob/master/reports/summary.md#request
        :type params: dict
        :return: If ``as_pdf`` is ``True``, then a ``bytes`` object containing the report as a PDF document is
            returned. Otherwise, a ``dict`` as described in the following resources is returned:

            - https://github.com/toggl/toggl_api_docs/blob/master/reports.md#successful-response
            - https://github.com/toggl/toggl_api_docs/blob/master/reports/summary.md#response
        :rtype: dict | bytes
        """
        if as_pdf:
            return self._do_get("summary.pdf", decode_json=False, **params)

        return self._do_get("summary", **params)
