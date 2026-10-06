from __future__ import annotations

"""
Master Skill & Tool Registry - Führende Quelle für alle organisierten Skills und Tools

Dieses Modul dient als zentrale Anlaufstelle und Dokumentation für:
- Alle eingebauten (builtin) Skills
- Alle verfügbaren Tools (builtin, MCP, custom)
- Methoden zur Akquirierung neuer Fähigkeiten
- Best Practices für Skill- und Tool-Entwicklung

Architektur:
-----------
1. SKILL MANAGEMENT
   - Skill Discovery: Automatische Erkennung in definierten Pfaden
   - Skill Loading: Dynamisches Laden von SKILL.md Dateien
   - Skill Registry: Verbindung zu externen Skill-Registries
   
2. TOOL MANAGEMENT  
   - Builtin Tools: Kernfunktionalitäten (bash, read_file, write_file, etc.)
   - MCP Tools: Model Context Protocol Integration
   - Custom Tools: Benutzerdefinierte Tools
   
3. AKQUIRIERUNGSMETHODEN
   - Skill Creation: Erstellen neuer Skills
   - Tool Registration: Registrieren neuer Tools
   - Dependency Management: Abhängigkeitsverwaltung
"""

from vibe.core.skills.models import SkillInfo, SkillSource


# =============================================================================
# SEKTION 1: KERN-SKILLS (Built-in Skills)
# =============================================================================

"""
Built-in Skills sind vordefinierte Fähigkeiten, die direkt mit Vibe ausgeliefert werden.
Sie sind schreibgeschützt und haben höchste Priorität bei Namenskonflikten.
"""

BUILTIN_SKILLS_REGISTRY = {
    "vibe": {
        "name": "vibe",
        "description": "Mistral Vibe Selbstbewusstsein - Vollständiges Wissen über die Anwendung",
        "category": "system",
        "priority": 1000,
        "dependencies": [],
        "required_tools": ["read_file", "grep", "bash"],
        "documentation": "vibe/core/skills/builtins/vibe.py",
    },
    "skill-creator": {
        "name": "skill-creator", 
        "description": "Erstellung, Aktualisierung und Löschung von Vibe Skills",
        "category": "development",
        "priority": 900,
        "dependencies": [],
        "required_tools": ["write_file", "read_file", "edit"],
        "documentation": "vibe/core/skills/builtins/skill_creator.py",
    },
}


# =============================================================================
# SEKTION 2: TOOL-KATEGORISIERUNG
# =============================================================================

"""
Tools werden in Kategorien organisiert, um die Auffindbarkeit und Verwaltung zu erleichtern.
Jede Kategorie hat spezifische Verantwortungsbereiche und Verwendungszwecke.
"""

TOOL_CATEGORIES = {
    # System- und Dateioperationen
    "file_operations": {
        "description": "Tools für Datei- und Verzeichnisoperationen",
        "tools": [
            {
                "name": "read_file",
                "description": "Liest den Inhalt von Dateien",
                "permission": "ASK",
                "category": "file_operations",
                "built_in": True,
                "documentation": "vibe/core/tools/builtins/read_file.py",
            },
            {
                "name": "write_file", 
                "description": "Erstellt oder überschreibt Dateien",
                "permission": "ASK",
                "category": "file_operations",
                "built_in": True,
                "documentation": "vibe/core/tools/builtins/write_file.py",
            },
            {
                "name": "edit",
                "description": "Bearbeitet bestehende Dateien",
                "permission": "ASK", 
                "category": "file_operations",
                "built_in": True,
                "documentation": "vibe/core/tools/builtins/edit.py",
            },
        ],
    },
    
    # Shell- und Prozessoperationen
    "shell_operations": {
        "description": "Tools für Shell-Befehle und Prozessausführung",
        "tools": [
            {
                "name": "bash",
                "description": "Führt Shell-Befehle aus (POSIX)",
                "permission": "ASK",
                "category": "shell_operations", 
                "built_in": True,
                "documentation": "vibe/core/tools/builtins/bash.py",
            },
            {
                "name": "git_bash",
                "description": "Git Bash für Windows-Systeme",
                "permission": "ASK",
                "category": "shell_operations",
                "built_in": True,
                "documentation": "vibe/core/tools/builtins/git_bash.py",
            },
            {
                "name": "windows_shell",
                "description": "Windows-spezifische Shell-Operationen",
                "permission": "ASK",
                "category": "shell_operations",
                "built_in": True,
                "documentation": "vibe/core/tools/builtins/windows_shell.py",
            },
        ],
    },
    
    # Such- und Analyse-Tools
    "search_analysis": {
        "description": "Tools für Suche und Code-Analyse",
        "tools": [
            {
                "name": "grep",
                "description": "Suche in Dateien mit regulären Ausdrücken",
                "permission": "ASK",
                "category": "search_analysis",
                "built_in": True,
                "documentation": "vibe/core/tools/builtins/grep.py",
            },
            {
                "name": "web_search",
                "description": "Suche im Web nach Informationen",
                "permission": "ASK",
                "category": "search_analysis",
                "built_in": True,
                "documentation": "vibe/core/tools/builtins/web_search.py",
            },
        ],
    },
    
    # Netzwerk- und Web-Tools
    "network_web": {
        "description": "Tools für Netzwerk- und Web-Operationen",
        "tools": [
            {
                "name": "web_fetch",
                "description": "Lädt Inhalte von Web-URLs",
                "permission": "ASK", 
                "category": "network_web",
                "built_in": True,
                "documentation": "vibe/core/tools/builtins/web_fetch.py",
            },
        ],
    },
    
    # MCP (Model Context Protocol) Tools
    "mcp_tools": {
        "description": "Tools, die über das Model Context Protocol integriert werden",
        "tools": [],  # Dynamisch geladen
        "dynamic": True,
    },
    
    # Aufgaben- und Projektmanagement
    "task_management": {
        "description": "Tools für Aufgaben- und Projektmanagement",
        "tools": [
            {
                "name": "todo",
                "description": "Verwaltet Todo-Listen",
                "permission": "ASK",
                "category": "task_management",
                "built_in": True,
                "documentation": "vibe/core/tools/builtins/todo.py",
            },
            {
                "name": "task",
                "description": "Erstellt und verwaltet Aufgaben",
                "permission": "ASK",
                "category": "task_management", 
                "built_in": True,
                "documentation": "vibe/core/tools/builtins/task.py",
            },
        ],
    },
    
    # Benutzerinteraktion
    "user_interaction": {
        "description": "Tools für Benutzerinteraktion und Feedback",
        "tools": [
            {
                "name": "ask_user_question",
                "description": "Stellt dem Benutzer Fragen",
                "permission": "ALWAYS",
                "category": "user_interaction",
                "built_in": True,
                "documentation": "vibe/core/tools/builtins/ask_user_question.py",
            },
            {
                "name": "exit_plan_mode",
                "description": "Verwaltet den Exit-Plan-Modus",
                "permission": "ALWAYS",
                "category": "user_interaction",
                "built_in": True,
                "documentation": "vibe/core/tools/builtins/exit_plan_mode.py",
            },
        ],
    },
}


# =============================================================================
# SEKTION 3: SKILL DISCOVERY PFADHIERARCHIE
# =============================================================================

"""
Skill-Discovery folgt einer strikten Hierarchie. Die erste Übereinstimmung gewinnt.
Built-in Skills haben höchste Priorität und sind schreibgeschützt.
"""

SKILL_DISCOVERY_HIERARCHY = [
    {
        "scope": "builtin",
        "path": "vibe/core/skills/builtins/",
        "priority": 1000,
        "read_only": True,
        "description": "Eingebaute Vibe Skills",
    },
    {
        "scope": "registry", 
        "path": "~/.vibe/registry_skills/",
        "priority": 900,
        "read_only": False,
        "description": "Skills aus dem Registry (materialisiert)",
    },
    {
        "scope": "project",
        "path": ".vibe/skills/",
        "priority": 800,
        "read_only": False,
        "requires_trust": True,
        "description": "Projekt-spezifische Skills",
    },
    {
        "scope": "project",
        "path": ".agents/skills/",
        "priority": 700,
        "read_only": False,
        "requires_trust": True,
        "description": "Projekt-spezifische Skills (alternativ)",
    },
    {
        "scope": "user",
        "path": "~/.vibe/skills/",
        "priority": 600,
        "read_only": False,
        "description": "Benutzer-globale Skills",
    },
    {
        "scope": "user",
        "path": "~/.agents/skills/",
        "priority": 500,
        "read_only": False,
        "description": "Benutzer-globale Skills (alternativ)",
    },
]


# =============================================================================
# SEKTION 4: TOOL DISCOVERY PFADHIERARCHIE
# =============================================================================

"""
Tool-Discovery folgt einer ähnlichen Hierarchie wie Skills.
Built-in Tools haben höchste Priorität.
"""

TOOL_DISCOVERY_HIERARCHY = [
    {
        "scope": "builtin",
        "path": "vibe/core/tools/builtins/",
        "priority": 1000,
        "read_only": True,
        "description": "Eingebaute Vibe Tools",
    },
    {
        "scope": "mcp",
        "path": "mcp_tools/",
        "priority": 900,
        "dynamic": True,
        "description": "MCP-integrierte Tools",
    },
    {
        "scope": "project",
        "path": ".vibe/tools/",
        "priority": 800,
        "read_only": False,
        "requires_trust": True,
        "description": "Projekt-spezifische Tools",
    },
    {
        "scope": "user",
        "path": "~/.vibe/tools/",
        "priority": 700,
        "read_only": False,
        "description": "Benutzer-definierte Tools",
    },
]


# =============================================================================
# SEKTION 5: AKQUIRIERUNGSMETHODEN
# =============================================================================

"""
Methoden zur Akquirierung neuer Skills und Tools.
Jede Methode bietet spezifische Vorteile und Anwendungsfälle.
"""

class SkillAcquisitionMethod:
    """Basis-Klasse für Skill-Akquirierungsmethoden"""
    
    def __init__(self, name: str, description: str, complexity: str):
        self.name = name
        self.description = description
        self.complexity = complexity  # "low", "medium", "high"
    
    def execute(self, **kwargs) -> dict:
        """Führt die Akquirierungsmethode aus"""
        raise NotImplementedError


class SkillCreationMethod(SkillAcquisitionMethod):
    """Erstellung eines neuen Skills von Grund auf"""
    
    def __init__(self):
        super().__init__(
            name="skill_creation",
            description="Erstellt einen neuen Skill basierend auf Benutzeranforderungen",
            complexity="medium"
        )
    
    def execute(self, name: str, description: str, instructions: str, 
                scope: str = "project", **kwargs) -> dict:
        """
        Erstellt einen neuen Skill
        
        Args:
            name: Skill-Name (slug-Format)
            description: Beschreibung für das Routing
            instructions: Anweisungen für das Modell
            scope: "project" oder "user"
            **kwargs: Zusätzliche Metadaten
        
        Returns:
            dict: Ergebnis der Skill-Erstellung
        """
        # Validierung
        import re
        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
            raise ValueError(f"Ungültiger Skill-Name: {name}")
        
        # Pfadbestimmung basierend auf Scope
        base_paths = {
            "project": ".vibe/skills/",
            "user": "~/.vibe/skills/"
        }
        base_path = base_paths.get(scope, ".vibe/skills/")
        skill_dir = f"{base_path}{name}/"
        
        return {
            "status": "created",
            "name": name,
            "path": skill_dir,
            "files": [
                {"name": "SKILL.md", "content": f"---\nname: {name}\ndescription: {description}\n---\n\n# {name.replace('-', ' ').title()}\n\n{instructions}"}
            ]
        }


class SkillFromTemplateMethod(SkillAcquisitionMethod):
    """Erstellung eines Skills basierend auf einer Vorlage"""
    
    def __init__(self):
        super().__init__(
            name="skill_from_template",
            description="Erstellt einen Skill aus einer vordefinierten Vorlage",
            complexity="low"
        )
    
    def execute(self, template_name: str, target_name: str, 
                scope: str = "project", **kwargs) -> dict:
        """
        Erstellt einen Skill aus einer Vorlage
        
        Args:
            template_name: Name der Vorlage
            target_name: Name des neuen Skills
            scope: "project" oder "user"
            **kwargs: Zusätzliche Parameter
        
        Returns:
            dict: Ergebnis der Skill-Erstellung
        """
        # Vorlagen-Registry (könnte erweitert werden)
        templates = {
            "code_review": {
                "description": "Code-Review Skill",
                "instructions": "Analysiere Code auf Qualitätsprobleme, Sicherheitslücken und Best Practices."
            },
            "documentation": {
                "description": "Dokumentations-Skill", 
                "instructions": "Generiere umfassende Dokumentation für Code und Projekte."
            },
            "testing": {
                "description": "Test-Skill",
                "instructions": "Erstelle und führe Tests für Code aus."
            }
        }
        
        if template_name not in templates:
            raise ValueError(f"Unbekannte Vorlage: {template_name}")
        
        template = templates[template_name]
        creator = SkillCreationMethod()
        return creator.execute(
            name=target_name,
            description=template["description"],
            instructions=template["instructions"],
            scope=scope,
            **kwargs
        )


class SkillFromRegistryMethod(SkillAcquisitionMethod):
    """Lädt einen Skill aus dem offiziellen Registry"""
    
    def __init__(self):
        super().__init__(
            name="skill_from_registry",
            description="Lädt einen Skill aus dem offiziellen Vibe Skill Registry",
            complexity="low"
        )
    
    def execute(self, skill_id: str, version: str = "latest", **kwargs) -> dict:
        """
        Lädt einen Skill aus dem Registry
        
        Args:
            skill_id: ID des Skills im Registry
            version: Version oder "latest"
            **kwargs: Zusätzliche Parameter
        
        Returns:
            dict: Ergebnis des Registry-Downloads
        """
        return {
            "status": "downloaded",
            "skill_id": skill_id,
            "version": version,
            "source": "registry",
            "message": f"Skill {skill_id}@{version} würde aus dem Registry geladen"
        }


class ToolRegistrationMethod(SkillAcquisitionMethod):
    """Registriert ein neues Tool"""
    
    def __init__(self):
        super().__init__(
            name="tool_registration",
            description="Registriert ein neues benuterdefiniertes Tool",
            complexity="high"
        )
    
    def execute(self, name: str, description: str, category: str, 
                permission: str = "ASK", **kwargs) -> dict:
        """
        Registriert ein neues Tool
        
        Args:
            name: Tool-Name
            description: Beschreibung des Tools
            category: Kategorie des Tools
            permission: Berechtigungsstufe (ALWAYS, ASK, NEVER)
            **kwargs: Zusätzliche Parameter
        
        Returns:
            dict: Ergebnis der Tool-Registrierung
        """
        # Validierung
        valid_permissions = ["ALWAYS", "ASK", "NEVER"]
        if permission not in valid_permissions:
            raise ValueError(f"Ungültige Berechtigung: {permission}")
        
        # Erstelle Tool-Struktur
        tool_structure = {
            "name": name,
            "description": description,
            "category": category,
            "permission": permission,
            "built_in": False,
            "custom": True,
            "documentation": f"~/.vibe/tools/{name}.py"
        }
        
        # Füge zu der entsprechenden Kategorie hinzu
        if category in TOOL_CATEGORIES:
            TOOL_CATEGORIES[category]["tools"].append(tool_structure)
        else:
            TOOL_CATEGORIES[category] = {
                "description": f"Benutzerdefinierte Kategorie: {category}",
                "tools": [tool_structure]
            }
        
        return {
            "status": "registered",
            "tool": tool_structure,
            "message": f"Tool {name} wurde in Kategorie {category} registriert"
        }


# =============================================================================
# SEKTION 6: BEST PRACTICES
# =============================================================================

"""
Best Practices für die Entwicklung von Skills und Tools.
"""

SKILL_DEVELOPMENT_BEST_PRACTICES = {
    "naming": {
        "description": "Namenskonventionen für Skills",
        "rules": [
            "Verwende nur Kleinbuchstaben, Zahlen und Bindestriche",
            "Maximale Länge: 64 Zeichen",
            "Muster: ^[a-z0-9]+(-[a-z0-9]+)*$",
            "Vermeide Namenskonflikte mit Built-in Skills",
        ]
    },
    "structure": {
        "description": "Struktur von Skills",
        "rules": [
            "Jeder Skill ist ein Verzeichnis mit einer SKILL.md Datei",
            "SKILL.md muss YAML-Frontmatter enthalten",
            "Frontmatter-Felder: name, description (erforderlich)",
            "Optionale Felder: user-invocable, allowed-tools, license, compatibility, metadata",
            "Unterstützungsdateien nur bei Bedarf hinzufügen",
        ]
    },
    "documentation": {
        "description": "Dokumentation von Skills",
        "rules": [
            "Klare und präzise Beschreibung im Frontmatter",
            "Anweisungen sollten spezifisch und handlungsorientiert sein",
            "Beispiele und Use Cases hinzufügen",
            "Abhängigkeiten und Voraussetzungen dokumentieren",
        ]
    },
    "testing": {
        "description": "Testen von Skills",
        "rules": [
            "Skills sollten in Isolation getestet werden",
            "Verwende /reload zum Neuladen von Skills während der Entwicklung",
            "Teste mit verschiedenen Modellen und Konfigurationen",
            "Validiere Frontmatter-Daten",
        ]
    }
}


TOOL_DEVELOPMENT_BEST_PRACTICES = {
    "naming": {
        "description": "Namenskonventionen für Tools",
        "rules": [
            "Verwende snake_case für Tool-Namen",
            "Name sollte die Funktion klar widerspiegeln",
            "Vermeide Namenskonflikte mit Built-in Tools",
        ]
    },
    "implementation": {
        "description": "Implementierung von Tools",
        "rules": [
            "Erbe von BaseTool",
            "Implementiere async def run(args, ctx: InvokeContext)",
            "Verwende Pydantic-Modelle für Argumente",
            "Yield Events für progressive Ausgabe",
            "Raise ToolError für Benutzerfehler",
            "Raise ToolPermissionError für Berechtigungsprobleme",
        ]
    },
    "permissions": {
        "description": "Berechtigungen für Tools",
        "rules": [
            "ALWAYS: Immer erlaubt, keine Rückfrage",
            "ASK: Rückfrage beim Benutzer",
            "NEVER: Niemals erlaubt",
            "Verwende ASK als Standard für potenziell gefährliche Operationen",
            "Verwende ALWAYS für sichere, häufig verwendete Tools",
        ]
    },
    "error_handling": {
        "description": "Fehlerbehandlung in Tools",
        "rules": [
            "Fange spezifische Exceptions und konvertiere zu ToolError",
            "Biete klare Fehlermeldungen für Benutzer",
            "Logge detaillierte Fehler für Debugging",
            "Vermeide das Leaken von sensiblen Informationen",
        ]
    }
}


# =============================================================================
# SEKTION 7: INTEGRATION MIT VIBE
# =============================================================================

"""
Integration des Master Skill Registry mit dem bestehenden Vibe-System.
"""

class MasterSkillRegistry:
    """
    Hauptklasse für den Zugriff auf das Master Skill & Tool Registry.
    
    Diese Klasse bietet:
    - Zentralen Zugriff auf alle Skills und Tools
    - Suchfunktionalität
    - Akquirierungsmethoden
    - Best Practices und Dokumentation
    """
    
    def __init__(self):
        self.builtin_skills = BUILTIN_SKILLS_REGISTRY
        self.tool_categories = TOOL_CATEGORIES
        self.skill_discovery_hierarchy = SKILL_DISCOVERY_HIERARCHY
        self.tool_discovery_hierarchy = TOOL_DISCOVERY_HIERARCHY
        self.acquisition_methods = {
            "skill_creation": SkillCreationMethod(),
            "skill_from_template": SkillFromTemplateMethod(),
            "skill_from_registry": SkillFromRegistryMethod(),
            "tool_registration": ToolRegistrationMethod(),
        }
    
    def get_skill_info(self, skill_name: str) -> dict | None:
        """Holt Informationen zu einem Skill"""
        return self.builtin_skills.get(skill_name)
    
    def get_tool_info(self, tool_name: str) -> dict | None:
        """Holt Informationen zu einem Tool"""
        for category, tools in self.tool_categories.items():
            for tool in tools.get("tools", []):
                if tool.get("name") == tool_name:
                    tool["category"] = category
                    return tool
        return None
    
    def search_skills(self, query: str) -> list[dict]:
        """Durchsucht alle Skills nach einem Suchbegriff"""
        results = []
        query_lower = query.lower()
        
        for skill_name, skill_info in self.builtin_skills.items():
            if (query_lower in skill_name.lower() or 
                query_lower in skill_info.get("description", "").lower()):
                results.append({
                    "name": skill_name,
                    "type": "builtin",
                    **skill_info
                })
        
        return results
    
    def search_tools(self, query: str) -> list[dict]:
        """Durchsucht alle Tools nach einem Suchbegriff"""
        results = []
        query_lower = query.lower()
        
        for category, tools in self.tool_categories.items():
            for tool in tools.get("tools", []):
                if (query_lower in tool.get("name", "").lower() or 
                    query_lower in tool.get("description", "").lower()):
                    tool_copy = tool.copy()
                    tool_copy["category"] = category
                    results.append(tool_copy)
        
        return results
    
    def list_skills_by_category(self) -> dict:
        """Listet alle Skills nach Kategorie"""
        # Für Built-in Skills
        categorized = {"builtin": list(self.builtin_skills.values())}
        return categorized
    
    def list_tools_by_category(self) -> dict:
        """Listet alle Tools nach Kategorie"""
        return self.tool_categories
    
    def get_acquisition_method(self, method_name: str) -> SkillAcquisitionMethod | None:
        """Holt eine spezifische Akquirierungsmethode"""
        return self.acquisition_methods.get(method_name)
    
    def list_acquisition_methods(self) -> dict:
        """Listet alle verfügbaren Akquirierungsmethoden"""
        return {
            name: {
                "description": method.description,
                "complexity": method.complexity
            }
            for name, method in self.acquisition_methods.items()
        }
    
    def get_best_practices(self, resource_type: str = "skill") -> dict:
        """Holt Best Practices für Skills oder Tools"""
        practices = {
            "skill": SKILL_DEVELOPMENT_BEST_PRACTICES,
            "tool": TOOL_DEVELOPMENT_BEST_PRACTICES
        }
        return practices.get(resource_type, {})
    
    def get_discovery_hierarchy(self, resource_type: str = "skill") -> list:
        """Holt die Discovery-Hierarchie für Skills oder Tools"""
        hierarchies = {
            "skill": self.skill_discovery_hierarchy,
            "tool": self.tool_discovery_hierarchy
        }
        return hierarchies.get(resource_type, [])


# =============================================================================
# SEKTION 8: EXPORT
# =============================================================================

"""
Export der Hauptklasse und wichtiger Konstanten für den Zugriff von außen.
"""

# Erstelle eine globale Instanz des Registry
_master_registry: MasterSkillRegistry | None = None


def get_master_registry() -> MasterSkillRegistry:
    """Holt die globale Instanz des Master Skill Registry"""
    global _master_registry
    if _master_registry is None:
        _master_registry = MasterSkillRegistry()
    return _master_registry


# Skill Information für das System
MASTER_REGISTRY_SKILL = SkillInfo(
    name="master-skill-registry",
    description=(
        "Zentrale Quelle für alle organisierten Skills und Tools. "
        "Bietet Zugriff auf Built-in Skills, Tool-Kategorien, "
        "Akquirierungsmethoden und Best Practices."
    ),
    user_invocable=True,
    source=SkillSource.BUILTIN,
)


__all__ = [
    "MasterSkillRegistry",
    "get_master_registry",
    "MASTER_REGISTRY_SKILL",
    "BUILTIN_SKILLS_REGISTRY",
    "TOOL_CATEGORIES",
    "SKILL_DISCOVERY_HIERARCHY",
    "TOOL_DISCOVERY_HIERARCHY",
    "SkillAcquisitionMethod",
    "SkillCreationMethod",
    "SkillFromTemplateMethod",
    "SkillFromRegistryMethod",
    "ToolRegistrationMethod",
    "SKILL_DEVELOPMENT_BEST_PRACTICES",
    "TOOL_DEVELOPMENT_BEST_PRACTICES",
]
