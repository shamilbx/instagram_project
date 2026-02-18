"""
Integration tests for POST /api/posts/{id}/comments/ endpoint.

These tests exercise the full Django request/response cycle — routing,
view, service, and database — while mocking only the Instagram HTTP
client so that no real network calls are made during the test run.

Test scenarios:
    1. Successful comment creation (DB record + API response).
    2. Post does not exist in the local database → 404.
    3. Post exists locally but the Instagram media has been deleted → 404.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from app.models import Comment, Post


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

INSTAGRAM_COMMENT_ID = "17858893269000001"
INSTAGRAM_MEDIA_ID = "17896129349000001"


def _make_post(instagram_id: str = INSTAGRAM_MEDIA_ID) -> Post:
    """Factory — create and return a saved Post fixture."""
    return Post.objects.create(instagram_id=instagram_id, caption="Test caption")


def _url(post_id: int) -> str:
    """Resolve the comment-create URL for a given post PK."""
    return reverse("comment-create", kwargs={"post_id": post_id})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def api_client() -> APIClient:
    """Return a DRF test client."""
    return APIClient()


@pytest.fixture()
def post(db) -> Post:
    """A Post that exists in the test database."""
    return _make_post()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCreateCommentSuccess:
    """
    Scenario 1: Happy path — comment is created in the DB and the API
    returns 201 with the correct payload.
    """

    def test_returns_201_with_comment_data(
        self, api_client: APIClient, post: Post
    ) -> None:
        """Response status must be 201 and contain the new comment's fields."""
        mock_response: dict[str, Any] = {"id": INSTAGRAM_COMMENT_ID}

        with patch(
            "app.services.instagram_client.requests.post",
            return_value=_mock_ok_response(mock_response),
        ):
            response = api_client.post(
                _url(post.pk),
                {"text": "Great photo!"},
                format="json",
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["text"] == "Great photo!"
        assert data["instagram_comment_id"] == INSTAGRAM_COMMENT_ID
        assert data["post"] == post.pk

    def test_comment_record_is_saved_to_database(
        self, api_client: APIClient, post: Post
    ) -> None:
        """A Comment row must be persisted in the DB after a successful request."""
        mock_response: dict[str, Any] = {"id": INSTAGRAM_COMMENT_ID}

        assert Comment.objects.count() == 0

        with patch(
            "app.services.instagram_client.requests.post",
            return_value=_mock_ok_response(mock_response),
        ):
            api_client.post(
                _url(post.pk),
                {"text": "Saved to DB!"},
                format="json",
            )

        assert Comment.objects.count() == 1
        comment = Comment.objects.first()
        assert comment is not None
        assert comment.text == "Saved to DB!"
        assert comment.instagram_comment_id == INSTAGRAM_COMMENT_ID
        assert comment.post_id == post.pk

    def test_instagram_api_called_with_correct_args(
        self, api_client: APIClient, post: Post
    ) -> None:
        """The client must call the Instagram API with the post's media ID."""
        mock_response: dict[str, Any] = {"id": INSTAGRAM_COMMENT_ID}

        with patch(
            "app.services.instagram_client.requests.post",
            return_value=_mock_ok_response(mock_response),
        ) as mock_post:
            api_client.post(
                _url(post.pk),
                {"text": "Check args"},
                format="json",
            )

        mock_post.assert_called_once()
        call_url: str = mock_post.call_args[0][0]
        assert post.instagram_id in call_url


@pytest.mark.django_db
class TestCreateCommentPostNotFound:
    """
    Scenario 2: The requested post_id does not exist in the local database.
    The endpoint must return 404 without touching the Instagram API.
    """

    def test_returns_404_when_post_missing(self, api_client: APIClient) -> None:
        """Response status must be 404."""
        non_existent_post_id = 9999

        with patch("app.services.instagram_client.requests.post") as mock_post:
            response = api_client.post(
                _url(non_existent_post_id),
                {"text": "Hello"},
                format="json",
            )
            mock_post.assert_not_called()

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_error_detail_mentions_post_id(self, api_client: APIClient) -> None:
        """Response body must contain a meaningful error message."""
        non_existent_post_id = 9999

        with patch("app.services.instagram_client.requests.post"):
            response = api_client.post(
                _url(non_existent_post_id),
                {"text": "Hello"},
                format="json",
            )

        assert "detail" in response.json()

    def test_no_comment_created_in_db(self, api_client: APIClient) -> None:
        """No Comment row must be written when the post is missing."""
        with patch("app.services.instagram_client.requests.post"):
            api_client.post(
                _url(9999),
                {"text": "Nothing should be saved"},
                format="json",
            )

        assert Comment.objects.count() == 0


@pytest.mark.django_db
class TestCreateCommentMediaDeletedOnInstagram:
    """
    Scenario 3: The post exists in the local DB but the corresponding
    Instagram media object has been deleted.  The Instagram API returns a
    'media not found' error (code 100, subcode 33).  The endpoint must
    return 404 and must NOT save a Comment record.
    """

    def test_returns_404_when_instagram_media_deleted(
        self, api_client: APIClient, post: Post
    ) -> None:
        """Response status must be 404."""
        with patch(
            "app.services.instagram_client.requests.post",
            return_value=_mock_media_not_found_response(),
        ):
            response = api_client.post(
                _url(post.pk),
                {"text": "Commenting on deleted media"},
                format="json",
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_error_detail_is_present(
        self, api_client: APIClient, post: Post
    ) -> None:
        """Response body must include a ``detail`` key with an error description."""
        with patch(
            "app.services.instagram_client.requests.post",
            return_value=_mock_media_not_found_response(),
        ):
            response = api_client.post(
                _url(post.pk),
                {"text": "Commenting on deleted media"},
                format="json",
            )

        data = response.json()
        assert "detail" in data
        assert len(data["detail"]) > 0

    def test_no_comment_saved_when_media_deleted(
        self, api_client: APIClient, post: Post
    ) -> None:
        """A Comment row must NOT be persisted when the API signals the media is gone."""
        with patch(
            "app.services.instagram_client.requests.post",
            return_value=_mock_media_not_found_response(),
        ):
            api_client.post(
                _url(post.pk),
                {"text": "Should not be saved"},
                format="json",
            )

        assert Comment.objects.count() == 0


@pytest.mark.django_db
class TestCreateCommentValidation:
    """Additional validation edge-cases."""

    def test_returns_400_when_text_missing(
        self, api_client: APIClient, post: Post
    ) -> None:
        """Missing ``text`` field must yield 400."""
        with patch("app.services.instagram_client.requests.post"):
            response = api_client.post(_url(post.pk), {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_returns_400_when_text_is_empty_string(
        self, api_client: APIClient, post: Post
    ) -> None:
        """Empty string must be rejected."""
        with patch("app.services.instagram_client.requests.post"):
            response = api_client.post(
                _url(post.pk), {"text": ""}, format="json"
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_returns_502_on_unexpected_instagram_error(
        self, api_client: APIClient, post: Post
    ) -> None:
        """Unexpected Instagram API errors must yield 502 Bad Gateway."""
        with patch(
            "app.services.instagram_client.requests.post",
            return_value=_mock_instagram_error_response(
                code=10, message="Application does not have permission"
            ),
        ):
            response = api_client.post(
                _url(post.pk), {"text": "Hello"}, format="json"
            )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY


# ---------------------------------------------------------------------------
# Mock response factories
# ---------------------------------------------------------------------------

def _mock_ok_response(body: dict[str, Any]) -> MagicMock:
    """Return a mock that looks like a successful ``requests.Response``."""
    mock = MagicMock()
    mock.ok = True
    mock.status_code = 200
    mock.json.return_value = body
    return mock


def _mock_media_not_found_response() -> MagicMock:
    """
    Return a mock that simulates the Instagram API's response when a
    media object has been deleted (code=100, error_subcode=33).
    """
    mock = MagicMock()
    mock.ok = False
    mock.status_code = 400
    mock.json.return_value = {
        "error": {
            "message": "Invalid parameter",
            "type": "OAuthException",
            "code": 100,
            "error_subcode": 33,
            "fbtrace_id": "ABC123",
        }
    }
    return mock


def _mock_instagram_error_response(code: int, message: str) -> MagicMock:
    """Return a generic Instagram API error mock."""
    mock = MagicMock()
    mock.ok = False
    mock.status_code = 400
    mock.json.return_value = {
        "error": {
            "message": message,
            "type": "OAuthException",
            "code": code,
            "fbtrace_id": "XYZ789",
        }
    }
    return mock
