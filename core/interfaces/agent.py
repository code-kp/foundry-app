from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Type

from core.registry import Register

from .tools import ToolLike, ensure_tools


@dataclass(frozen=True)
class Agent:
    """Normalized agent definition used by runtime and registry."""

    name: str
    description: str
    system_prompt: str
    tools: Sequence[ToolLike]
    skills_dir: Optional[str] = None
    model: Optional[str] = None


class AgentModule:
    """
    Class-based authoring surface for agent modules.

    Example:
      @register_agent_class
      class SupportTriage(AgentModule):
          name = "Support Triage"
          description = "..."
          system_prompt = "..."
          tools = [...]
    """

    name: str = ""
    description: str = ""
    system_prompt: str = ""
    tools: Sequence[ToolLike] = ()
    skills_dir: Optional[str] = None
    model: Optional[str] = None


def define_agent(
    *,
    name: str,
    description: str,
    system_prompt: str,
    tools: Optional[Sequence[ToolLike]] = None,
    skills_dir: Optional[str] = None,
    model: Optional[str] = None,
) -> Agent:
    return Agent(
        name=name,
        description=description,
        system_prompt=system_prompt,
        tools=tuple(ensure_tools(tools)),
        skills_dir=skills_dir,
        model=model,
    )


def register_agent(agent: Agent) -> Agent:
    return Register.register(Agent, agent.name, agent, overwrite=True)


def agent_from_class(agent_cls: Type[AgentModule]) -> Agent:
    if not getattr(agent_cls, "name", "").strip():
        raise ValueError("Agent class {name} is missing a non-empty 'name'.".format(name=agent_cls.__name__))
    if not getattr(agent_cls, "system_prompt", "").strip():
        raise ValueError(
            "Agent class {name} is missing a non-empty 'system_prompt'.".format(name=agent_cls.__name__)
        )

    return define_agent(
        name=agent_cls.name,
        description=getattr(agent_cls, "description", "") or agent_cls.name,
        system_prompt=agent_cls.system_prompt,
        tools=getattr(agent_cls, "tools", ()),
        skills_dir=getattr(agent_cls, "skills_dir", None),
        model=getattr(agent_cls, "model", None),
    )


def register_agent_class(agent_cls: Type[AgentModule]) -> Type[AgentModule]:
    definition = agent_from_class(agent_cls)
    register_agent(definition)
    setattr(agent_cls, "__agent_definition__", definition)
    return agent_cls
