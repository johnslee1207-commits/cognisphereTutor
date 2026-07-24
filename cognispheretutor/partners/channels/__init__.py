"""Chat channels module with plugin architecture."""

from cognispheretutor.partners.channels.base import BaseChannel
from cognispheretutor.partners.channels.manager import ChannelManager

__all__ = ["BaseChannel", "ChannelManager"]
