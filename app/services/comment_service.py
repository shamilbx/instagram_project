"""
Comment service layer.

All business logic for creating comments lives here.  Views stay thin —
they delegate to this service which orchestrates DB reads/writes and the
Instagram API call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models import Comment, Post
from app.services.instagram_client import InstagramClient, InstagramAPIError, MediaNotFoundError

if TYPE_CHECKING:
    pass


class PostNotFoundError(Exception):
    """Raised when the requested Post does not exist in the local DB."""


class CommentService:
    """
    Orchestrates comment creation across the local DB and Instagram API.

    Keeps Views free of business logic by providing a single entry-point
    method that callers can use without knowing about the underlying
    persistence or external API details.
    """

    def __init__(self, instagram_client: InstagramClient | None = None) -> None:
        self._client: InstagramClient = instagram_client or InstagramClient()

    def create_comment(self, post_id: int, text: str) -> Comment:
        """
        Create a comment on an Instagram post and persist it locally.

        This method implements the following sequence:
        1. Verify the post exists in the local DB — raise ``PostNotFoundError`` otherwise.
        2. Send the comment to the Instagram Graph API via ``InstagramClient``.
        3. On success, save the new ``Comment`` record to the database and return it.

        Any ``InstagramAPIError`` raised by the client propagates to the caller
        (i.e., the View) so it can be translated into an appropriate HTTP response.

        Args:
            post_id: Primary key of the local ``Post`` record.
            text:    Comment text to publish.

        Returns:
            The newly created :class:`Comment` instance (already saved).

        Raises:
            PostNotFoundError:   The post does not exist in the local DB.
            MediaNotFoundError:  The post's Instagram media no longer exists.
            InstagramAPIError:   Any other Instagram API failure.
        """
        # Step 1 — verify local post exists
        try:
            post: Post = Post.objects.get(pk=post_id)
        except Post.DoesNotExist:
            raise PostNotFoundError(f"Post with id={post_id} not found")

        # Step 2 — publish to Instagram
        api_response = self._client.create_comment(
            media_id=post.instagram_id,
            message=text,
        )

        # Step 3 — persist locally
        instagram_comment_id: str = api_response["id"]
        comment = Comment.objects.create(
            post=post,
            instagram_comment_id=instagram_comment_id,
            text=text,
        )
        return comment
