"""Integrations package for Sales RPG AI.

External service integrations for meeting capture and transcript streaming.
"""

from .vexa_client import VexaClient, VexaConfig

__all__ = ["VexaClient", "VexaConfig"]
