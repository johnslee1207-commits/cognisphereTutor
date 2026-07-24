"""Message bus module for decoupled channel-agent communication."""

from cognispheretutor.partners.bus.events import InboundMessage, OutboundMessage
from cognispheretutor.partners.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
