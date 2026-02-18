"""Models for Instagram posts and comments."""

from django.db import models


class Post(models.Model):
    """
    Represents an Instagram post stored in the local database.

    Stores a reference to an Instagram media object so that comments
    can be created via the Instagram Graph API.
    """

    instagram_id: str = models.CharField(
        max_length=255,
        unique=True,
        help_text="Instagram media object ID",
    )
    caption: str = models.TextField(blank=True, default="")
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "posts"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Post(id={self.pk}, instagram_id={self.instagram_id})"


class Comment(models.Model):
    """
    Represents a comment that was successfully posted to Instagram.

    After the Instagram API call succeeds, the comment is persisted
    locally to keep a record of all published comments.
    """

    post: Post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    instagram_comment_id: str = models.CharField(
        max_length=255,
        help_text="Instagram comment ID returned by the API",
    )
    text: str = models.TextField()
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comments"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Comment(id={self.pk}, post_id={self.post_id})"
