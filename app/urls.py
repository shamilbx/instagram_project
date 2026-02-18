"""URL patterns for the app."""

from django.urls import path

from app.views import CommentCreateView

urlpatterns = [
    path("posts/<int:post_id>/comments/", CommentCreateView.as_view(), name="comment-create"),
]
