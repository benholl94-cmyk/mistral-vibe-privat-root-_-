from __future__ import annotations

from vibe.core.skills.builtins.master_skill_registry import (
    MASTER_REGISTRY_SKILL,
    get_master_registry,
)
from vibe.core.skills.builtins.skill_creator import SKILL as SKILL_CREATOR_SKILL
from vibe.core.skills.builtins.vibe import SKILL as VIBE_SKILL

__all__ = [
    "MASTER_REGISTRY_SKILL",
    "SKILL_CREATOR_SKILL",
    "VIBE_SKILL",
    "get_master_registry",
]

BUILTIN_SKILLS = [
    VIBE_SKILL,
    SKILL_CREATOR_SKILL,
    MASTER_REGISTRY_SKILL,
]
