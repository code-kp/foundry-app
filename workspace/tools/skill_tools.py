from __future__ import annotations

from core.interfaces.tools import current_progress, tool
from core.skill_store import SkillStore
from workspace import SKILLS_ROOT


SKILL_STORE = SkillStore(SKILLS_ROOT)


@tool(description="Search relevant markdown skill chunks for a query.")
def search_skills(query: str, max_results: int = 3) -> dict:
    progress = current_progress()
    progress.comment("Searching indexed skill chunks.", query=query, max_results=max_results)
    results = SKILL_STORE.search(query=query, max_results=max_results)
    progress.comment("Skill search completed.", matches=len(results))
    return {"query": query, "results": results}


@tool(description="List discovered skills with their ids, types, and summaries.")
def list_skill_files() -> dict:
    progress = current_progress()
    skills = SKILL_STORE.describe()
    progress.comment("Listed discovered skills.", skills=len(skills))
    return {"skills": skills}


@tool(description="Read a markdown skill by skill id or relative file path.")
def read_skill_file(file_name: str) -> dict:
    progress = current_progress()
    skill = SKILL_STORE.get_skill(file_name) or SKILL_STORE.get_skill_by_source(file_name)
    if skill is None:
        raise FileNotFoundError("Skill not found: {name}".format(name=file_name))
    progress.comment("Reading skill file.", file=skill.source, skill_id=skill.id)
    return {
        "skill": {
            "id": skill.id,
            "title": skill.title,
            "type": skill.skill_type,
            "summary": skill.summary,
            "mode": skill.mode,
            "source": skill.source,
        },
        "content": skill.body,
    }


__all__ = ["search_skills", "list_skill_files", "read_skill_file"]
