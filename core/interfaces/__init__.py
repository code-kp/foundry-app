"""Interfaces for defining agents and tools."""

from .agent import Agent, AgentModule, define_agent, register_agent, register_agent_class
from .skills import SkillDefinition
from .tools import (
    ToolDefinition,
    ToolLike,
    create_tool,
    register_tool,
    register_tools,
    resolve_tool,
    tool,
)

__all__ = [
    "Agent",
    "AgentModule",
    "SkillDefinition",
    "ToolDefinition",
    "ToolLike",
    "define_agent",
    "register_agent",
    "register_agent_class",
    "create_tool",
    "register_tool",
    "register_tools",
    "resolve_tool",
    "tool",
]
