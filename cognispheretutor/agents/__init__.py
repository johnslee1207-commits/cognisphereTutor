"""
Agents Module - Unified agent system for OpenTutor.

This module provides a unified BaseAgent class and module-specific agents:
- research: Deep research agents (DecomposeAgent, ResearchAgent, etc.)
- question: Question generation agents (ReAct architecture, separate base)
- chat: ``AgenticChatPipeline`` — single-loop chat on the agentic engine
  (Deep Solve also runs here, via the solve loop capability)

Note: ``co_writer`` and ``book`` are independent top-level modules under
``cognispheretutor/`` (e.g. ``cognispheretutor.co_writer``, ``cognispheretutor.book``). They
still inherit from :class:`BaseAgent` defined here but are not part of
the ``cognispheretutor.agents`` package.

Usage:
    from cognispheretutor.agents.base_agent import BaseAgent

    class MyAgent(BaseAgent):
        async def process(self, *args, **kwargs):
            ...
"""

from .base_agent import BaseAgent
from .chat import ChatAgent, SessionManager

__all__ = ["BaseAgent", "ChatAgent", "SessionManager"]
