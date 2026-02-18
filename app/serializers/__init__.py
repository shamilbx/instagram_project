"""DRF serializers for Post and Comment resources."""

from rest_framework import serializers

from app.models import Comment, Post


class CommentSerializer(serializers.ModelSerializer):
    """Serializes a Comment instance to/from JSON."""

    class Meta:
        model = Comment
        fields = ["id", "post", "instagram_comment_id", "text", "created_at"]
        read_only_fields = ["id", "instagram_comment_id", "created_at"]


class CreateCommentSerializer(serializers.Serializer):
    """Validates the request body for comment creation."""

    text: serializers.CharField = serializers.CharField(
        min_length=1,
        max_length=2200,
        help_text="Comment text (Instagram limit: 2 200 characters)",
    )
