"""Configuration package — exports the shared settings singleton."""

from config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
