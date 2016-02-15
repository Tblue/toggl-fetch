import json
import logging
import time
from abc import *

import requests
import requests.exceptions


USER_AGENT = "toggl-fetch-api-client/1.0 (tilman+toggldev@ax86.net)"

_logger = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(self, message):
        self._message = message

    def __str__(self):
        return self._message


class AuthenticationError(APIError):
    pass


class RateLimitingError(APIError):
    pass


class _APIBase(metaclass=ABCMeta):
    def __init__(self, api_base_url, api_token):
        self._api_base_url = api_base_url

        self._session = requests.Session()
        self._session.auth = (api_token, "api_token")

        # Set the user agent
        orig_user_agent = self._session.headers.get("user-agent")
        new_user_agent = USER_AGENT

        if orig_user_agent:
            new_user_agent += " " + orig_user_agent

        self._session.headers["user-agent"] = new_user_agent
        self._session.params["user_agent"] = USER_AGENT

    def _do_get(self, path, attempts=3, decode_json=True, **params):
        for attempt in range(1, attempts + 1):
            try:
                resp = self._session.get(self._api_base_url + path, params=params)
                self._check_error(resp)

                if decode_json:
                    return resp.json()

                return resp.content
            except (RateLimitingError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                if attempt == attempts:
                    raise

                time.sleep(1)

    @abstractmethod
    def _check_error(self, response):
        pass


class Toggl(_APIBase):
    API_BASE_URL = "https://www.toggl.com/api/v8/"

    def __init__(self, *args, **kwargs):
        super().__init__(self.API_BASE_URL, *args, **kwargs)

    def _check_error(self, response):
        if response.status_code == 404:
            raise APIError("; ".join(response.json()))

        if response.status_code == 403:
            raise AuthenticationError("Invalid API token")

        if response.status_code == 429:
            # Rate limiting triggered
            raise RateLimitingError("Request limit reached")

        response.raise_for_status()

    def get_workspaces(self):
        return self._do_get("workspaces")

    def get_workspace_by_name(self, name):
        for workspace in self.get_workspaces():
            if workspace["name"] == name:
                return workspace["id"]

        return None


class TogglReports(_APIBase):
    API_BASE_URL = "https://toggl.com/reports/api/v2/"

    def __init__(self, *args, **kwargs):
        super().__init__(self.API_BASE_URL, *args, **kwargs)

    def _check_error(self, response, log_warnings=True):
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

        try:
            data = response.json()
        except json.JSONDecodeError:
            data = {}

        if "error" not in data:
            response.raise_for_status()
        else:
            raise APIError(
                    "Error #{error[code]}: {error[message]} - {error[tip]}".format(error=data["error"])
            )

    def test_400(self):
        return self._do_get("error400")

    def get_summary(self, as_pdf=False, **params):
        if as_pdf:
            return self._do_get("summary.pdf", decode_json=False, **params)

        return self._do_get("summary", **params)
