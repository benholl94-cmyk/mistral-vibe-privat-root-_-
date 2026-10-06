from __future__ import annotations

"""
Skill Registry Tool - Zugriff auf das Master Skill & Tool Registry

Dieses Tool ermöglicht den Zugriff auf das zentrale Master Skill Registry,
um Informationen über verfügbare Skills und Tools abzurufen.
"""

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from vibe.core.skills.builtins.master_skill_registry import get_master_registry
from vibe.core.tools.base import BaseTool, BaseToolConfig, InvokeContext
from vibe.core.tools.models import ToolPermission

if TYPE_CHECKING:
    from vibe.core.types import ToolStreamEvent


class SkillRegistryQueryArgs(BaseModel):
    """Argumente für Registry-Abfragen"""
    
    query_type: str = Field(
        default="skills",
        description="Typ der Abfrage: 'skills', 'tools', 'categories', 'best_practices'",
    )
    query: str = Field(
        default="",
        description="Suchbegriff für Skills oder Tools",
    )
    category: str = Field(
        default="",
        description="Filter nach Kategorie (für Tools)",
    )
    resource_type: str = Field(
        default="skill",
        description="Ressourcentyp für Best Practices: 'skill' oder 'tool'",
    )
    detailed: bool = Field(
        default=False,
        description="Detaillierte Ausgabe (mehr Informationen)",
    )


class SkillRegistryResult(BaseModel):
    """Ergebnis einer Registry-Abfrage"""
    
    success: bool = Field(
        default=True,
        description="Ob die Abfrage erfolgreich war",
    )
    query_type: str = Field(
        default="",
        description="Typ der durchgeführten Abfrage",
    )
    results: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Ergebnisse der Abfrage",
    )
    count: int = Field(
        default=0,
        description="Anzahl der Ergebnisse",
    )
    message: str = Field(
        default="",
        description="Zusätzliche Nachrichten",
    )


class SkillRegistryTool(BaseTool[SkillRegistryQueryArgs, SkillRegistryResult]):
    """
    Tool für den Zugriff auf das Master Skill & Tool Registry.
    
    Ermöglicht:
    - Suche nach Skills und Tools
    - Auflistung aller verfügbaren Skills und Tools
    - Abruf von Kategorien und Best Practices
    - Detaillierte Informationen zu einzelnen Skills/Tools
    """
    
    name = "skill_registry"
    description = (
        "Zugriff auf das zentrale Master Skill & Tool Registry. "
        "Ermöglicht Suche, Auflistung und Abruf von Informationen "
        "über verfügbare Skills, Tools, Kategorien und Best Practices."
    )
    
    permission = ToolPermission.ALWAYS
    config = BaseToolConfig(permission=ToolPermission.ALWAYS)
    
    async def run(
        self, args: SkillRegistryQueryArgs, ctx: InvokeContext
    ) -> list[ToolStreamEvent]:
        """Führt eine Registry-Abfrage aus"""
        
        master_registry = get_master_registry()
        
        # Verarbeite die Abfrage basierend auf dem Typ
        if args.query_type == "skills":
            results = self._search_skills(master_registry, args)
        elif args.query_type == "tools":
            results = self._search_tools(master_registry, args)
        elif args.query_type == "categories":
            results = self._list_categories(master_registry, args)
        elif args.query_type == "best_practices":
            results = self._get_best_practices(master_registry, args)
        elif args.query_type == "acquisition_methods":
            results = self._list_acquisition_methods(master_registry, args)
        elif args.query_type == "discovery_hierarchy":
            results = self._get_discovery_hierarchy(master_registry, args)
        else:
            results = self._list_all(master_registry, args)
        
        # Erstelle das Ergebnis
        result = SkillRegistryResult(
            success=True,
            query_type=args.query_type,
            results=results,
            count=len(results),
            message=f"Gefunden {len(results)} Ergebnisse für Abfrage: {args.query_type}"
        )
        
        # Yield das Ergebnis als Event
        yield self.create_result_event(result.model_dump())
    
    def _search_skills(
        self, registry, args: SkillRegistryQueryArgs
    ) -> list[dict[str, Any]]:
        """Durchsucht Skills"""
        if args.query:
            return registry.search_skills(args.query)
        else:
            # Liste alle Skills
            all_skills = []
            for skill_name, skill_info in registry.builtin_skills.items():
                skill_data = {
                    "type": "builtin",
                    "name": skill_name,
                    **skill_info
                }
                if args.detailed:
                    skill_data["full_info"] = skill_info
                all_skills.append(skill_data)
            return all_skills
    
    def _search_tools(
        self, registry, args: SkillRegistryQueryArgs
    ) -> list[dict[str, Any]]:
        """Durchsucht Tools"""
        if args.query:
            return registry.search_tools(args.query)
        elif args.category:
            # Liste Tools einer spezifischen Kategorie
            categories = registry.list_tools_by_category()
            if args.category in categories:
                tools = categories[args.category].get("tools", [])
                return [
                    {**tool, "category": args.category} 
                    for tool in tools
                ]
            return []
        else:
            # Liste alle Tools
            all_tools = []
            for category, category_data in registry.list_tools_by_category().items():
                for tool in category_data.get("tools", []):
                    all_tools.append({**tool, "category": category})
            return all_tools
    
    def _list_categories(
        self, registry, args: SkillRegistryQueryArgs
    ) -> list[dict[str, Any]]:
        """Listet alle Kategorien"""
        categories = []
        
        # Skill-Kategorien (aus Built-in Skills)
        skill_categories = set()
        for skill_info in registry.builtin_skills.values():
            if "category" in skill_info:
                skill_categories.add(skill_info["category"])
        
        for cat in skill_categories:
            categories.append({
                "type": "skill_category",
                "name": cat,
                "description": f"Skill-Kategorie: {cat}"
            })
        
        # Tool-Kategorien
        tool_categories = registry.list_tools_by_category()
        for cat_name, cat_data in tool_categories.items():
            if cat_name not in skill_categories:
                categories.append({
                    "type": "tool_category",
                    "name": cat_name,
                    "description": cat_data.get("description", f"Tool-Kategorie: {cat_name}"),
                    "tool_count": len(cat_data.get("tools", []))
                })
        
        return categories
    
    def _get_best_practices(
        self, registry, args: SkillRegistryQueryArgs
    ) -> list[dict[str, Any]]:
        """Holt Best Practices"""
        best_practices = registry.get_best_practices(args.resource_type)
        
        if not best_practices:
            return [{"message": f"Keine Best Practices für {args.resource_type} gefunden"}]
        
        results = []
        for section, rules in best_practices.items():
            results.append({
                "section": section,
                "description": rules.get("description", ""),
                "rules": rules.get("rules", [])
            })
        
        return results
    
    def _list_acquisition_methods(
        self, registry, args: SkillRegistryQueryArgs
    ) -> list[dict[str, Any]]:
        """Listet Akquirierungsmethoden"""
        methods = registry.list_acquisition_methods()
        
        results = []
        for name, info in methods.items():
            results.append({
                "name": name,
                "description": info["description"],
                "complexity": info["complexity"]
            })
        
        return results
    
    def _get_discovery_hierarchy(
        self, registry, args: SkillRegistryQueryArgs
    ) -> list[dict[str, Any]]:
        """Holt die Discovery-Hierarchie"""
        hierarchy = registry.get_discovery_hierarchy(
            "skill" if args.resource_type == "skill" else "tool"
        )
        
        results = []
        for entry in hierarchy:
            results.append({
                "scope": entry.get("scope", "unknown"),
                "path": entry.get("path", ""),
                "priority": entry.get("priority", 0),
                "read_only": entry.get("read_only", False),
                "requires_trust": entry.get("requires_trust", False),
                "description": entry.get("description", "")
            })
        
        return results
    
    def _list_all(
        self, registry, args: SkillRegistryQueryArgs
    ) -> list[dict[str, Any]]:
        """Listet alle verfügbaren Ressourcen"""
        result = {
            "skills": self._search_skills(registry, args),
            "tools": self._search_tools(registry, args),
            "categories": self._list_categories(registry, args),
            "summary": {
                "total_skills": len(registry.builtin_skills),
                "total_tool_categories": len(registry.list_tools_by_category()),
                "acquisition_methods": list(registry.list_acquisition_methods().keys())
            }
        }
        return [result]
