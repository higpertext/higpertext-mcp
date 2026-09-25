"""Single source of truth for native agent-adapter capabilities.

The renderers intentionally remain separate because each target has a different
file format and lifecycle.  This module owns the compatibility matrix: a new
assistant or a changed native event must be added here first, not duplicated in
several renderers.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class AdapterSpec:
    id: str
    documentation_url: str
    instruction_files: tuple[str, ...]
    hook_settings_path: str
    # Profile-server event name -> native configuration event name.
    hook_events: Mapping[str, str]
    # Canonical tool name -> native tool name(s), separated by | when needed.
    tool_aliases: Mapping[str, str]
    skills_dir: str | None = None
    agents_dir: str | None = None
    agents_extension: str | None = None
    agents_format: str | None = None
    # None means that the adapter delegates model validation to its provider.
    # A non-empty tuple contains supported exact names or prefixes ending in *.
    model_patterns: tuple[str, ...] | None = None
    # This repository does not invent a workflow convention.  Playbooks are
    # rendered as native skills or agents when the target supports them.
    workflows_dir: str | None = None
    status: str = "native"
    limitations: tuple[str, ...] = ()

    @property
    def supports_hooks(self) -> bool:
        return bool(self.hook_events)

    @property
    def supports_skills(self) -> bool:
        return self.skills_dir is not None

    @property
    def supports_agents(self) -> bool:
        return self.agents_dir is not None and self.agents_format is not None

    @property
    def supports_workflows(self) -> bool:
        return self.workflows_dir is not None

    def supports_model(self, model: str) -> bool:
        if not model:
            return False
        if self.model_patterns is None:
            return True
        return any(
            model.startswith(pattern[:-1]) if pattern.endswith("*") else model == pattern
            for pattern in self.model_patterns
        )


def _mapping(value: dict[str, str]) -> Mapping[str, str]:
    return MappingProxyType(value)


_COMMON_HOOK_EVENTS = _mapping({
    "PreToolUse": "PreToolUse",
    "PostToolUse": "PostToolUse",
    "UserPromptSubmit": "UserPromptSubmit",
    "Stop": "Stop",
    "PreCompact": "PreCompact",
})

_COMMON_TOOLS = _mapping({})


ADAPTERS: Mapping[str, AdapterSpec] = MappingProxyType({
    "claude": AdapterSpec(
        id="claude",
        documentation_url="https://docs.anthropic.com/en/docs/claude-code",
        instruction_files=("CLAUDE.md", ".claude/rules/{profile}.md"),
        hook_settings_path=".claude/settings.json",
        hook_events=_COMMON_HOOK_EVENTS,
        tool_aliases=_COMMON_TOOLS,
        skills_dir=".claude/skills",
        agents_dir=".claude/agents",
        agents_extension=".md",
        agents_format="claude-markdown",
        model_patterns=("claude-*", "opus", "sonnet", "haiku"),
        limitations=("ACTION_AUTHORIZED belongs to the gateway/controller, not a hook.",),
    ),
    "codex": AdapterSpec(
        id="codex",
        documentation_url="https://developers.openai.com/codex",
        instruction_files=("AGENTS.md",),
        hook_settings_path=".codex/hooks.json",
        hook_events=_COMMON_HOOK_EVENTS,
        tool_aliases=_COMMON_TOOLS,
        skills_dir=".agents/skills",
        agents_dir=".codex/agents",
        agents_extension=".toml",
        agents_format="codex-toml",
        model_patterns=("gpt-*", "o1", "o3", "o4"),
        limitations=("ACTION_AUTHORIZED belongs to the gateway/controller, not a hook.",),
    ),
    "gemini": AdapterSpec(
        id="gemini",
        documentation_url="https://github.com/google-gemini/gemini-cli/tree/main/docs/hooks",
        instruction_files=("GEMINI.md",),
        hook_settings_path=".gemini/settings.json",
        hook_events=_mapping({
            "PreToolUse": "BeforeTool",
            "PostToolUse": "AfterTool",
            "UserPromptSubmit": "BeforeAgent",
            "PreCompact": "PreCompress",
        }),
        tool_aliases=_mapping({
            "Bash": "run_shell_command",
            "PowerShell": "run_shell_command",
            "Read": "read_file",
            "Write": "write_file",
            "Edit": "replace",
        }),
        skills_dir=".gemini/skills",
        limitations=(
            "Gemini CLI no tiene aquí un formato de subagente materializado por AgentService.",
            "Los hooks deben emitir JSON por stdout; texto libre rompe el contrato nativo.",
        ),
    ),
    "copilot": AdapterSpec(
        id="copilot",
        documentation_url="https://docs.github.com/en/copilot/reference/hooks-reference",
        instruction_files=(".github/copilot-instructions.md",),
        hook_settings_path=".github/hooks/higpertext.json",
        hook_events=_mapping({
            "PreToolUse": "preToolUse",
            "PostToolUse": "postToolUse",
            "UserPromptSubmit": "userPromptSubmitted",
            "Stop": "agentStop",
        }),
        tool_aliases=_mapping({
            "Bash": "bash",
            "PowerShell": "powershell",
            "Read": "view",
            "Write": "create",
            "Edit": "edit",
        }),
        skills_dir=".github/skills",
        agents_dir=".github/agents",
        agents_extension=".md",
        agents_format="copilot-markdown",
        limitations=("La disponibilidad de hooks depende de Copilot CLI/cloud agent.",),
    ),
    "antigravity": AdapterSpec(
        id="antigravity",
        documentation_url="",
        instruction_files=("AGENTS.md",),
        hook_settings_path=".agents/hooks.json",
        hook_events=_mapping({"PreToolUse": "PreToolUse", "PostToolUse": "PostToolUse", "Stop": "Stop"}),
        tool_aliases=_mapping({
            "Bash": "run_command",
            "PowerShell": "run_command",
            "Read": "view_file",
            "Write": "write_to_file",
            "Edit": "replace_file_content|multi_replace_file_content",
        }),
        skills_dir=".agents/skills",
        status="bridge",
        limitations=("No hay en este repositorio una especificación pública estable del protocolo nativo.",),
    ),
    "opencode": AdapterSpec(
        id="opencode",
        documentation_url="https://opencode.ai/docs",
        instruction_files=("AGENTS.md",),
        hook_settings_path=".opencode/plugins/higpertext.js",
        hook_events=_mapping({"PreToolUse": "tool.execute.before", "PostToolUse": "tool.execute.after"}),
        tool_aliases=_mapping({"Bash": "bash", "Read": "read", "Write": "write", "Edit": "edit"}),
        skills_dir=".opencode/skills",
        agents_dir=".opencode/agents",
        agents_extension=".md",
        agents_format="opencode-markdown",
        status="bridge",
        limitations=("Hooks se materializan mediante un plugin JavaScript compatible con tool.execute.",),
    ),
    "grok": AdapterSpec(
        id="grok",
        documentation_url="https://docs.x.ai",
        instruction_files=(".grok/rules/{profile}.md",),
        hook_settings_path=".grok/hooks/higpertext.json",
        hook_events=_COMMON_HOOK_EVENTS,
        tool_aliases=_mapping({
            "Bash": "run_terminal_command",
            "PowerShell": "run_terminal_command",
            "Read": "read_file",
            "Write": "search_replace",
            "Edit": "search_replace",
        }),
        skills_dir=".grok/skills",
        agents_dir=".grok/agents",
        agents_extension=".md",
        agents_format="grok-markdown",
        model_patterns=("grok-*",),
        status="native",
        limitations=(
            "ACTION_AUTHORIZED belongs to the gateway/controller, not a hook.",
            "Los matchers se escriben con los nombres nativos de Grok; el runtime también acepta alias de Claude.",
        ),
    ),
})

SUPPORTED = tuple(ADAPTERS)


def get(adapter: str) -> AdapterSpec:
    try:
        return ADAPTERS[adapter]
    except KeyError as exc:
        raise ValueError(f"adapter not supported: {adapter}") from exc


def specs_for(assistants: list[str] | tuple[str, ...] | None) -> tuple[AdapterSpec, ...]:
    selected = list(dict.fromkeys(assistants or SUPPORTED))
    invalid = sorted(set(selected) - set(SUPPORTED))
    if invalid:
        raise ValueError(f"adapters no soportados: {', '.join(invalid)}")
    return tuple(get(name) for name in selected)


def assistants_with(feature: str) -> tuple[str, ...]:
    return tuple(spec.id for spec in ADAPTERS.values() if getattr(spec, f"supports_{feature}"))
