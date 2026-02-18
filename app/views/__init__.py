"""
API Views for comment management.

Views are intentionally thin: they handle HTTP concerns only (request
parsing, response formatting, status codes) and delegate all business
logic to the service layer.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from app.serializers import CommentSerializer, CreateCommentSerializer
from app.services import (
    CommentService,
    InstagramAPIError,
    MediaNotFoundError,
    PostNotFoundError,
)


class CommentCreateView(APIView):
    """
    POST /api/posts/{id}/comments/

    Creates a comment on the specified Instagram post.

    Request body:
        ``{ "text": "your comment" }``

    Responses:
        201 — comment created successfully.
        400 — invalid request body.
        404 — post not found in local DB, or media deleted from Instagram.
        502 — Instagram API returned an unexpected error.
    """

    def post(self, request: Request, post_id: int) -> Response:
        """Handle POST — validate input, delegate to service, return result."""
        # Validate request payload
        input_serializer = CreateCommentSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(input_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        text: str = input_serializer.validated_data["text"]
        service = CommentService()

        try:
            comment = service.create_comment(post_id=post_id, text=text)
        except PostNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except MediaNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except InstagramAPIError as exc:
            return Response(
                {"detail": f"Instagram API error: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        output_serializer = CommentSerializer(comment)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
