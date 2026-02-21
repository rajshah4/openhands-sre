from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_SKILLS_ROOT = Path('.agents') / 'skills'


@dataclass
class SkillSelection:
    skill_id: str
    skill_path: Path
    strategy_hint: str


SCENARIO_TO_SKILL = {
    'stale_lockfile': 'stale-lockfile',
    'bad_env_config': 'bad-env-config',
    'readiness_probe_fail': 'readiness-probe-fail',
    'port_mismatch': 'port-mismatch',
}

SKILL_HINTS = {
    'stale-lockfile': (
        'Apply the stale-lockfile skill runbook: inspect /tmp/service.lock under /tmp, '
        'remove stale lockfile, and verify with curl.'
    ),
    'bad-env-config': (
        'Apply the bad-env-config skill runbook: validate REQUIRED_API_KEY env config, '
        'apply minimal fix, and verify with curl.'
    ),
    'readiness-probe-fail': (
        'Apply the readiness-probe-fail skill runbook: check /tmp/ready.flag readiness signal, '
        'restore readiness state, and verify with curl.'
    ),
    'port-mismatch': (
        'Apply the port-mismatch skill runbook: inspect ports 5000 and 5001, '
        'correct bind/probe mismatch, and verify with curl.'
    ),
}

KEYWORD_TO_SKILL: list[tuple[str, str]] = [
    ('lock', 'stale-lockfile'),
    ('required_api_key', 'bad-env-config'),
    ('missing env', 'bad-env-config'),
    ('ready.flag', 'readiness-probe-fail'),
    ('readiness', 'readiness-probe-fail'),
    ('port', 'port-mismatch'),
    ('5001', 'port-mismatch'),
]


def _resolve_skill_id(scenario_id: str | None, error_report: str) -> str:
    if scenario_id and scenario_id in SCENARIO_TO_SKILL:
        return SCENARIO_TO_SKILL[scenario_id]

    report = (error_report or '').lower()
    for needle, skill_id in KEYWORD_TO_SKILL:
        if needle in report:
            return skill_id
    return 'stale-lockfile'


def list_skill_ids(skills_root: str | Path = DEFAULT_SKILLS_ROOT) -> list[str]:
    root = Path(skills_root)
    if not root.exists():
        return []
    return sorted([p.name for p in root.iterdir() if p.is_dir() and (p / 'SKILL.md').exists()])


def select_skill(
    *,
    scenario_id: str | None,
    error_report: str,
    skills_root: str | Path = DEFAULT_SKILLS_ROOT,
) -> SkillSelection:
    skill_id = _resolve_skill_id(scenario_id, error_report)
    skill_path = Path(skills_root) / skill_id / 'SKILL.md'
    if not skill_path.exists():
        available = ', '.join(list_skill_ids(skills_root)) or 'none'
        raise FileNotFoundError(f"Skill file not found: {skill_path}. Available skills: {available}")

    return SkillSelection(
        skill_id=skill_id,
        skill_path=skill_path,
        strategy_hint=SKILL_HINTS.get(skill_id, 'Apply the selected skill runbook and verify with curl.'),
    )


def format_skill_catalog(skill_ids: Iterable[str]) -> str:
    items = sorted(skill_ids)
    if not items:
        return '(no skills found)'
    return ', '.join(items)
