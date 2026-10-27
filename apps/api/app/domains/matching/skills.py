import re

# Canonical vocabulary shared by document parsing, matching and resume optimization.
# Aliases are matched with word boundaries so "storage" never matches "rag".
SKILL_GROUPS: dict[str, set[str]] = {
    "python": {"python", "py"},
    "fastapi": {"fastapi"},
    "vue": {"vue", "vue.js", "vue3", "vue 3"},
    "typescript": {"typescript", "ts"},
    "javascript": {"javascript", "js"},
    "rag": {"rag", "检索增强生成", "retrieval augmented generation"},
    "langchain": {"langchain"},
    "langgraph": {"langgraph"},
    "postgresql": {"postgres", "postgresql"},
    "pgvector": {"pgvector"},
    "mysql": {"mysql"},
    "redis": {"redis"},
    "sqlalchemy": {"sqlalchemy"},
    "docker": {"docker", "容器化"},
    "git": {"git"},
    "pytest": {"pytest"},
    "pytorch": {"pytorch", "torch"},
    "transformers": {"transformers", "hugging face", "huggingface"},
    "llm": {"llm", "large language model", "大语言模型", "大模型"},
}

ALIAS_TO_CANONICAL = {
    alias: canonical for canonical, aliases in SKILL_GROUPS.items() for alias in aliases
}

DISPLAY_NAMES = {
    "python": "Python",
    "fastapi": "FastAPI",
    "vue": "Vue 3",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "rag": "RAG",
    "langchain": "LangChain",
    "langgraph": "LangGraph",
    "postgresql": "PostgreSQL",
    "pgvector": "pgvector",
    "mysql": "MySQL",
    "redis": "Redis",
    "sqlalchemy": "SQLAlchemy",
    "docker": "Docker",
    "git": "Git",
    "pytest": "pytest",
    "pytorch": "PyTorch",
    "transformers": "Transformers",
    "llm": "LLM",
}


def normalize_skill(skill: str) -> str:
    normalized = re.sub(r"\s+", " ", skill.strip().lower())
    return ALIAS_TO_CANONICAL.get(normalized, normalized)


def normalize_skills(skills: list[str]) -> set[str]:
    return {normalize_skill(skill) for skill in skills if skill.strip()}


def display_skill(skill: str) -> str:
    return DISPLAY_NAMES.get(skill, skill[:1].upper() + skill[1:] if skill else skill)


def contains_alias(text: str, alias: str) -> bool:
    if re.fullmatch(r"[a-z0-9 .+#-]+", alias):
        return bool(
            re.search(
                rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
                text,
                flags=re.IGNORECASE,
            )
        )
    return alias in text


def detect_skills(text: str) -> list[str]:
    """Return canonical skill keys mentioned in arbitrary text."""

    lowered = text.lower()
    return sorted(
        canonical
        for canonical, aliases in SKILL_GROUPS.items()
        if any(contains_alias(lowered, alias.lower()) for alias in aliases)
    )
