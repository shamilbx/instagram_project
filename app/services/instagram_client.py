"""
Instagram Graph API client.

This module provides a low-level HTTP client for the Instagram Graph API.
All network requests to Instagram are isolated here so they can be easily
mocked in tests without affecting any other application logic.
"""

from typing import Any

import requests
from django.conf import settings


class InstagramAPIError(Exception):
    """Raised when the Instagram API returns an error response."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class MediaNotFoundError(InstagramAPIError):
    """Raised when the requested Instagram media object does not exist."""


class InstagramClient:
    """
    HTTP client for the Instagram Graph API.

    Wraps the ``requests`` library and handles authentication, error
    parsing, and response normalisation so that callers only deal with
    clean Python objects or typed exceptions.
    """

    def __init__(self, access_token: str | None = None) -> None:
        self._access_token: str = access_token or settings.INSTAGRAM_ACCESS_TOKEN
        self._base_url: str = settings.INSTAGRAM_API_BASE_URL

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def create_comment(self, media_id: str, message: str) -> dict[str, Any]:
        """
        Publish a comment on an Instagram media object.

        Calls ``POST /{media_id}/comments`` on the Graph API.

        Args:
            media_id: Instagram media object ID to comment on.
            message:  Text content of the comment.

        Returns:
            A dict with at least ``{"id": "<instagram_comment_id>"}``.

        Raises:
            MediaNotFoundError: If the media object no longer exists on Instagram.
            InstagramAPIError:  For any other non-successful API response.
        """
        url = f"{self._base_url}/{media_id}/comments"
        payload = {
            "message": message,
            "access_token": self._access_token,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
        except requests.RequestException as exc:
            raise InstagramAPIError(f"Network error while calling Instagram API: {exc}") from exc

        return self._handle_response(response, media_id=media_id)

    def get_media(self, media_id: str) -> dict[str, Any]:
        """
        Fetch metadata for an Instagram media object.

        Args:
            media_id: Instagram media object ID.

        Returns:
            A dict containing media fields returned by the API.

        Raises:
            MediaNotFoundError: If the media object does not exist.
            InstagramAPIError:  For any other non-successful API response.
        """
        url = f"{self._base_url}/{media_id}"
        params = {
            "fields": "id,caption,media_type",
            "access_token": self._access_token,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
        except requests.RequestException as exc:
            raise InstagramAPIError(f"Network error while calling Instagram API: {exc}") from exc

        return self._handle_response(response, media_id=media_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _handle_response(
        self, response: requests.Response, *, media_id: str
    ) -> dict[str, Any]:
        """
        Parse a Graph API response and raise typed exceptions on failure.

        The Graph API returns HTTP 200 even for business-logic errors and
        embeds the error details inside ``response.json()["error"]``.
        This method normalises both transport-level and application-level
        errors into the same exception hierarchy.

        Args:
            response: Raw ``requests.Response`` from the API call.
            media_id: Passed through for error context.

        Returns:
            The parsed JSON body as a Python dict.

        Raises:
            MediaNotFoundError: When the API signals the media is missing.
            InstagramAPIError:  For all other error conditions.
        """
        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise InstagramAPIError(
                f"Invalid JSON response from Instagram API (status={response.status_code})"
            ) from exc

        if not response.ok or "error" in data:
            error = data.get("error", {})
            error_message: str = error.get("message", response.text)
            error_code: int = error.get("code", response.status_code)

            # Instagram returns code 100 / subcode 33 for missing objects
            error_subcode: int = error.get("error_subcode", 0)
            if error_code == 100 and error_subcode == 33:
                raise MediaNotFoundError(
                    f"Instagram media '{media_id}' was not found",
                    status_code=404,
                )

            raise InstagramAPIError(error_message, status_code=error_code)

        return data
