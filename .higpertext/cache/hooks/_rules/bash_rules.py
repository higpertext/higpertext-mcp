"""Reglas de evaluación para comandos Bash (PreToolUse:Bash).

Cada función recibe (cmd: str, root: Path) y retorna una RuleResult.
El entrypoint hook_bash_guard.py evalúa todas en cadena.

v2: RuleResult ahora carga rule_id/weight — necesarios para que
hook_bash_guard pueda registrar la decisión en AuditService (ver
audit_client.py) con trazabilidad de qué regla decidió qué, y con qué
peso (1-5, ver GovernanceRule.weight en el profile server). Las etapas
"precondition" (check_hard_blocks, check_deployment_gate) llevan peso fijo
5 — no negociable, nunca degradan. La etapa "policy" (check_profile_rules)
lee weight de profile_rules.json si está presente (rule.get("weight")); si
el generador de ese JSON todavía no lo incluye (pendiente en higpertext-mcp
al momento de escribir esto), cae a 5 para "block" / 3 para "context", el
mismo mapeo que usa domain.GovernanceRule.EffectiveWeight en el server Go.
"""

from __future__ import annotations
from .governance_adapter import get_bash_blocks, get_deployment_blocks
from .render import render_box
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RuleSeverity = Literal["continue", "context", "block"]


@dataclass
class RuleResult:
    severity: RuleSeverity
    message: str = ""
    capability: str = ""
    rule_id: str = ""
    weight: int = 0


# ── Patrones compartidos ───────────────────────────────────────────────────────
# v3: el whitelist exige que el comando COMPLETO empiece con un prefijo
# seguro y no tenga metacaracteres de encadenamiento — antes "sudo echo x"
# pasaba de largo porque \becho\b matcheaba "echo" en cualquier posición del
# string (bypass real, encontrado en pruebas post-incidente 2026-09-06), y
# "git add . && rm -rf /" pasaba por el mismo motivo vía
# _GIT_ADD_ONLY.search(cmd) sin anclar. Ahora ambos usan match() (ancla al
# inicio) y _CHAIN_METACHARS corta cualquier comando compuesto antes de
# evaluar el resto — un comando encadenado nunca se whitelistea entero,
# aunque su primer segmento sea seguro.

_CHAIN_METACHARS = re.compile(r"[;&|\n`]|\$\(")

_WHITELIST = re.compile(
    r"^\s*(git\s+checkout|git\s+merge|git\s+rebase|git\s+stash|git\s+tag|echo)\b"
)
_GIT_ADD_ONLY = re.compile(r"^\s*git\s+add\b")
_GIT_COMMIT_PRESENT = re.compile(r"\bgit\s+commit\b")


def is_whitelisted(cmd: str) -> bool:
    if _CHAIN_METACHARS.search(cmd):
        return False
    if "git commit" in cmd:
        return False
    if _WHITELIST.match(cmd):
        return True
    if _GIT_ADD_ONLY.match(cmd) and not _GIT_COMMIT_PRESENT.search(cmd):
        return True
    return False


# ── Regla 1: Bloques duros (sudo, git push) — etapa "precondition" ───────────
# Peso fijo 5: estos bloqueos no dependen de ninguna GovernanceRule
# configurable, son invariantes del entorno. Nunca se degradan a warn.


def check_hard_blocks(cmd: str, root: Path) -> RuleResult | None:
    hard_blocks = get_bash_blocks(root)
    for pattern, reason in hard_blocks:
        if re.search(pattern, cmd):
            return RuleResult(
                severity="block",
                message=render_box("HIGPERTEXT  ·  Bloqueado", [f"  ✗  {reason}"]),
                rule_id="hard-block",
                weight=5,
            )
    return None


# ── Regla 2: Deployment gate (deployment_gates.json) — etapa "precondition" ──


def check_deployment_gate(cmd: str, root: Path) -> RuleResult | None:
    """Warn/block sobre comandos de deploy según deployment_gates.json."""
    for pattern, reason, severity in get_deployment_blocks(root):
        if re.search(pattern, cmd, re.IGNORECASE):
            return RuleResult(
                severity=severity,
                message=render_box("HIGPERTEXT  ·  Deployment Gate", [f"  ⚠  {reason}"]),
                rule_id="deployment-gate",
                weight=5 if severity == "block" else 3,
            )
    return None


# ── Regla 3: reglas de perfil externo (desde _rules/profile_rules.json) ──────
# Etapa "policy": a diferencia de las dos anteriores, el peso viene de la
# GovernanceRule que originó cada entrada (renderizada acá por higpertext-mcp
# desde GovernanceService.ListRules) — no es fijo.


def check_profile_rules(cmd: str, root: Path) -> RuleResult | None:
    if not root:
        return None
    rules_file = Path(__file__).parent / "profile_rules.json"
    if not rules_file.exists():
        return None
    try:
        data = json.loads(rules_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for rule in data.get("rules", []):
        pattern = rule.get("pattern", "")
        if not pattern or not re.search(pattern, cmd):
            continue
        severity = rule.get("severity", "block")
        cap_id = rule.get("capability", "")
        reason = rule.get("reason", "")
        rule_id = rule.get("id", "") or (f"profile-rule:{cap_id}" if cap_id else f"profile-rule:{pattern[:24]}")
        weight = int(rule.get("weight", 0) or 0)
        if not (1 <= weight <= 5):
            weight = 5 if severity == "block" else 3
        default_example = f"mcp__higpertext__{cap_id.replace('.', '_', 1)}" if cap_id else ""
        example = rule.get("example", default_example)
        return RuleResult(
            severity=severity,
            capability=cap_id,
            rule_id=rule_id,
            weight=weight,
            message=render_box(
                "HIGPERTEXT  ·  Regla de perfil",
                [
                    f"  Comando detectado : {cmd}",
                    *([f"  Capacidad         : {cap_id}"] if cap_id else []),
                    f"  Motivo            : {reason}",
                    *([f"  Uso               : {example}"] if example else []),
                ],
            ),
        )
    return None
