from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _resolve_source(source: str) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    source_path = Path(source).expanduser()
    if source_path.exists():
        return source_path.resolve(), None

    tmpdir: tempfile.TemporaryDirectory[str] | None = tempfile.TemporaryDirectory(prefix="itbench-scenarios-")
    clone_dir = Path(tmpdir.name) / "repo"
    proc = subprocess.run(
        ["git", "clone", "--depth", "1", source, str(clone_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        tmpdir.cleanup()
        raise RuntimeError(f"Failed to clone {source}: {proc.stderr.strip()}")
    return clone_dir.resolve(), tmpdir


def _extract_doc_descriptions(scenarios_md: Path) -> dict[str, str]:
    if not scenarios_md.exists():
        return {}

    text = _read_text(scenarios_md)
    lines = text.splitlines()
    out: dict[str, str] = {}

    for idx, line in enumerate(lines):
        m = re.match(r"^###\s+Scenario\s+(\d+)\s*$", line.strip(), flags=re.IGNORECASE)
        if not m:
            continue
        scenario_id = m.group(1)
        description = ""
        for j in range(idx + 1, min(idx + 25, len(lines))):
            dm = re.match(r"^\*\*Description:\*\*\s*(.+?)\s*$", lines[j].strip())
            if dm:
                description = dm.group(1).strip()
                break
        if description:
            out[scenario_id] = description

    return out


def _extract_incident_spec(path: Path) -> dict[str, str]:
    text = _read_text(path)

    meta_id_match = re.search(r"(?m)^\s*id:\s*(\d+)\s*$", text)
    meta_id = meta_id_match.group(1).strip() if meta_id_match else ""

    # First scenario metadata name is the useful title in incident specs.
    name_match = re.search(r"(?m)^\s*name:\s*(.+?)\s*$", text)
    name = name_match.group(1).strip() if name_match else ""

    file_id_match = re.search(r"incident_(\d+)\.ya?ml$", path.name)
    file_id = file_id_match.group(1) if file_id_match else ""

    return {
        "file_id": file_id,
        "meta_id": meta_id,
        "name": name,
    }


def _expected_checks(text: str) -> list[str]:
    t = text.lower()
    if "readiness" in t or "containersnotready" in t:
        return ["kubectl describe pod <pod>", "readiness probe events"]
    if "port" in t or "network" in t or "gateway" in t or "dns" in t:
        return ["kubectl get svc -A", "kubectl describe svc <service>"]
    if "env" in t or "image" in t or "command" in t or "authentication" in t:
        return ["kubectl describe deployment <name>", "kubectl get events -A --sort-by=.lastTimestamp"]
    if "resource" in t or "quota" in t or "cpu" in t or "memory" in t or "oom" in t:
        return ["kubectl top pods -A", "kubectl describe quota -A"]
    return ["kubectl get pods -A", "kubectl get events -A --sort-by=.lastTimestamp"]


def _build_records(source_root: Path, source_subdir: str) -> list[dict[str, Any]]:
    sre_root = source_root / source_subdir
    incidents_dir = sre_root / "roles" / "incidents" / "files" / "specs"
    if not incidents_dir.exists():
        raise FileNotFoundError(f"incident specs directory not found: {incidents_dir}")

    doc_descriptions = _extract_doc_descriptions(sre_root / "docs" / "scenarios.md")

    rows: list[dict[str, Any]] = []
    for incident_path in sorted(incidents_dir.glob("incident_*.yaml")):
        parsed = _extract_incident_spec(incident_path)
        file_id = parsed.get("file_id", "")
        meta_id = parsed.get("meta_id", "")
        canonical_id = file_id or meta_id
        if not canonical_id:
            continue

        title = parsed.get("name", "")
        description = doc_descriptions.get(canonical_id, "")

        if title and description:
            error_report = f"ITBench incident {canonical_id}: {title}. {description}"
        elif title:
            error_report = f"ITBench incident {canonical_id}: {title}."
        elif description:
            error_report = f"ITBench incident {canonical_id}: {description}"
        else:
            error_report = f"ITBench incident {canonical_id}: imported from {incident_path.name}"

        row = {
            "scenario_id": f"itbench_incident_{canonical_id}",
            "error_report": error_report,
            "expected_first_checks": _expected_checks(error_report),
            "_source_path": str(incident_path.relative_to(source_root)),
            "_source_subdir": source_subdir,
        }
        rows.append(row)

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Import ITBench SRE incidents into training_data schema")
    parser.add_argument(
        "--source",
        default="https://github.com/itbench-hub/ITBench.git",
        help="Local path or git URL for ITBench repository",
    )
    parser.add_argument("--source-subdir", default="scenarios/sre", help="SRE subtree in source repo/path")
    parser.add_argument("--output", default="training_data/atlas_sre_scenarios.json")
    parser.add_argument("--include-source-meta", action="store_true", help="Keep internal _source_* fields")
    args = parser.parse_args()

    source_root, tmpdir = _resolve_source(args.source)
    try:
        rows = _build_records(source_root, args.source_subdir)
        if not rows:
            raise RuntimeError("No incident records discovered")

        if not args.include_source_meta:
            for row in rows:
                row.pop("_source_path", None)
                row.pop("_source_subdir", None)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

        print(f"[import] source={source_root}")
        print(f"[import] source_subdir={args.source_subdir}")
        print(f"[import] records_written={len(rows)}")
        print(f"[import] output={output_path}")
    finally:
        if tmpdir is not None:
            tmpdir.cleanup()


if __name__ == "__main__":
    main()
