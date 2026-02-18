"""App configuration."""

from django.apps import AppConfig


class AppConfig(AppConfig):
    """Configuration for the main app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "app"
