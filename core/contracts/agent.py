"""
Tests:
- tests/core/contracts/test_agent.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence, Type

import core.contracts.execution as contracts_execution
import core.contracts.hooks as contracts_hooks
import core.contracts.memory as contracts_memory
import core.contracts.skills as contracts_skills
import core.contracts.tools as contracts_tools
from core.registry import Register


VALID_RUNTIME_MODES = ("direct", "orchestrated")


@dataclass(frozen=True)
class Agent:
    """Normalized agent definition used by runtime and registry."""

    name: str
    description: str
    system_prompt: str
    tools: Sequence[contracts_tools.ToolLike]
    behavior_skills: Sequence[str] = ()
    knowledge_skills: Sequence[str] = ()
    skill_scopes: Sequence[str] = ()
    always_on_skills: Sequence[str] = ()
    skills_dir: Optional[str] = None
    model: Optional[str] = None
    runtime_mode: str = "direct"
    execution: contracts_execution.ExecutionConfig = field(
        default_factory=lambda: contracts_execution.DEFAULT_EXECUTION_CONFIG
    )
    memory: contracts_memory.MemoryConfig = field(
        default_factory=lambda: contracts_memory.DEFAULT_MEMORY_CONFIG
    )
    hooks: contracts_hooks.AgentHooks = field(
        default_factory=lambda: contracts_hooks.DEFAULT_AGENT_HOOKS
    )

    @property
    def behavior(self) -> Sequence[str]:
        return self.behavior_skills

    @property
    def knowledge(self) -> Sequence[str]:
        return self.knowledge_skills


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
    tools: Sequence[contracts_tools.ToolLike] = ()
    behavior: Sequence[str] = ()
    knowledge: Sequence[str] = ()
    behavior_skills: Sequence[str] = ()
    knowledge_skills: Sequence[str] = ()
    skill_scopes: Sequence[str] = ()
    always_on_skills: Sequence[str] = ()
    include_core_tools: bool = True
    core_toolsets: Sequence[str] = ()
    skills_dir: Optional[str] = None
    model: Optional[str] = None
    runtime_mode: str = "direct"
    execution: contracts_execution.ExecutionConfig = contracts_execution.DEFAULT_EXECUTION_CONFIG
    memory: contracts_memory.MemoryConfig = contracts_memory.DEFAULT_MEMORY_CONFIG
    hooks: contracts_hooks.AgentHooks = contracts_hooks.DEFAULT_AGENT_HOOKS


class OrchestratedAgentModule(AgentModule):
    """Class-based authoring surface for explicit plan-execute-replan-verify agents."""

    runtime_mode: str = "orchestrated"


def define_agent(
    *,
    name: str,
    description: str,
    system_prompt: str,
    tools: Optional[Sequence[contracts_tools.ToolLike]] = None,
    behavior: Optional[Sequence[str]] = None,
    knowledge: Optional[Sequence[str]] = None,
    behavior_skills: Optional[Sequence[str]] = None,
    knowledge_skills: Optional[Sequence[str]] = None,
    skill_scopes: Optional[Sequence[str]] = None,
    always_on_skills: Optional[Sequence[str]] = None,
    include_core_tools: bool = True,
    core_toolsets: Optional[Sequence[str]] = None,
    skills_dir: Optional[str] = None,
    model: Optional[str] = None,
    runtime_mode: str = "direct",
    execution: Optional[contracts_execution.ExecutionConfig] = None,
    memory: Optional[contracts_memory.MemoryConfig] = None,
    hooks: Optional[contracts_hooks.AgentHooks] = None,
) -> Agent:
    normalized_runtime_mode = str(runtime_mode or "direct").strip().lower()
    if normalized_runtime_mode not in VALID_RUNTIME_MODES:
        raise ValueError(
            "Unsupported runtime_mode: {value}. Expected one of: {allowed}.".format(
                value=runtime_mode,
                allowed=", ".join(VALID_RUNTIME_MODES),
            )
        )
    normalized_scopes = _resolve_skill_scopes(skill_scopes=skill_scopes, skills_dir=skills_dir)
    resolved_behavior = behavior if behavior is not None else behavior_skills
    resolved_knowledge = knowledge if knowledge is not None else knowledge_skills
    return Agent(
        name=name,
        description=description,
        system_prompt=system_prompt,
        tools=contracts_tools.ensure_tool_references(
            tools,
            include_core_tools=include_core_tools,
            core_toolsets=core_toolsets,
        ),
        behavior_skills=contracts_skills.ensure_skill_ids(resolved_behavior),
        knowledge_skills=contracts_skills.ensure_skill_ids(resolved_knowledge),
        skill_scopes=normalized_scopes,
        always_on_skills=contracts_skills.ensure_skill_ids(always_on_skills),
        skills_dir=skills_dir,
        model=model,
        runtime_mode=normalized_runtime_mode,
        execution=contracts_execution.ensure_execution_config(execution),
        memory=contracts_memory.ensure_memory_config(memory),
        hooks=contracts_hooks.ensure_agent_hooks(hooks),
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
        behavior=_resolve_class_skill_alias(agent_cls, "behavior", "behavior_skills"),
        knowledge=_resolve_class_skill_alias(agent_cls, "knowledge", "knowledge_skills"),
        skill_scopes=getattr(agent_cls, "skill_scopes", ()),
        always_on_skills=getattr(agent_cls, "always_on_skills", ()),
        include_core_tools=getattr(agent_cls, "include_core_tools", True),
        core_toolsets=getattr(agent_cls, "core_toolsets", ()),
        skills_dir=getattr(agent_cls, "skills_dir", None),
        model=getattr(agent_cls, "model", None),
        runtime_mode=getattr(agent_cls, "runtime_mode", "direct"),
        execution=getattr(agent_cls, "execution", contracts_execution.DEFAULT_EXECUTION_CONFIG),
        memory=getattr(agent_cls, "memory", contracts_memory.DEFAULT_MEMORY_CONFIG),
        hooks=getattr(agent_cls, "hooks", contracts_hooks.DEFAULT_AGENT_HOOKS),
    )


def register_agent_class(agent_cls: Type[AgentModule]) -> Type[AgentModule]:
    definition = agent_from_class(agent_cls)
    register_agent(definition)
    setattr(agent_cls, "__agent_definition__", definition)
    return agent_cls


def register_orchestrated_agent_class(
    agent_cls: Type[OrchestratedAgentModule],
) -> Type[OrchestratedAgentModule]:
    return register_agent_class(agent_cls)


def _resolve_skill_scopes(
    *,
    skill_scopes: Optional[Sequence[str]],
    skills_dir: Optional[str],
) -> tuple[str, ...]:
    normalized_scopes = list(contracts_skills.ensure_skill_scopes(skill_scopes))
    if not skills_dir:
        return tuple(normalized_scopes)

    compatibility_scope = str(skills_dir).strip().replace("/", ".")
    if not compatibility_scope:
        return tuple(normalized_scopes)

    for candidate in (compatibility_scope, "{scope}.*".format(scope=compatibility_scope)):
        if candidate not in normalized_scopes:
            normalized_scopes.append(candidate)
    return tuple(normalized_scopes)


def _resolve_class_skill_alias(
    agent_cls: Type[AgentModule],
    preferred_attr: str,
    legacy_attr: str,
) -> Sequence[str]:
    if preferred_attr in agent_cls.__dict__:
        return getattr(agent_cls, preferred_attr)
    return getattr(agent_cls, legacy_attr, ())
