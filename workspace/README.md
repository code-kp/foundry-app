# Workspace

Everything contributors need lives here:

- `agents/` for agent modules
- `tools/` for shared tool modules
- `skills/` for markdown skills

Rules:

- Agent ids come from the directory hierarchy under `agents/`
- Tool modules are loaded before agent modules, so agents can reference tools by name
- Skill ids come from the directory hierarchy under `skills/`
- Skill files should have frontmatter metadata (`title`, `type`, `summary`, `tags`, `triggers`, `mode`, `priority`)
- Agents select skills with `skill_scopes` and `always_on_skills`, not a single `skills_dir`

Example:

```python
from core.interfaces.agent import AgentModule, register_agent_class


@register_agent_class
class MyAgent(AgentModule):
    name = "My Agent"
    description = "What it does"
    system_prompt = "How it should behave"
    tools = ("get_current_utc_time", "search_skills")
    skill_scopes = ("general",)
    always_on_skills = ("general.persona",)
```
