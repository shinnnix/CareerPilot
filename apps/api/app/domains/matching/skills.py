import re

SKILL_GROUPS = {
    "python": {"python", "py"},
    "fastapi": {"fastapi"},
    "vue": {"vue", "vue.js", "vue3", "vue 3"},
    "typescript": {"typescript", "ts"},
    "rag": {"rag", "检索增强生成", "retrieval augmented generation"},
    "langchain": {"langchain"},
    "langgraph": {"langgraph"},
    "postgresql": {"postgres", "postgresql"},
    "pgvector": {"pgvector"},
    "docker": {"docker", "容器化"},
    "pytorch": {"pytorch", "torch"},
    "transformers": {"transformers", "hugging face", "huggingface"},
}

ALIAS_TO_CANONICAL = {
    alias: canonical for canonical, aliases in SKILL_GROUPS.items() for alias in aliases
}


def normalize_skill(skill: str) -> str:
    normalized = re.sub(r"\s+", " ", skill.strip().lower())
    return ALIAS_TO_CANONICAL.get(normalized, normalized)


def normalize_skills(skills: list[str]) -> set[str]:
    return {normalize_skill(skill) for skill in skills if skill.strip()}
