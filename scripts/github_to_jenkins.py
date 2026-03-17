#!/usr/bin/env python3
"""
Bridge GitHub issues or pull requests to the local Jenkins demo job.

Flow:
1. Resolve the target PR, either directly or from an issue reference.
2. Create an in-progress GitHub Check Run for the PR head SHA.
3. Trigger the local Jenkins pipeline.
4. Wait for the build result.
5. Complete the GitHub Check Run and optionally comment on the PR.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def run_gh(args: list[str]) -> str:
    result = subprocess.run(
        ["gh", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def gh_api(method: str, path: str, fields: dict[str, str] | None = None) -> str:
    args = ["api", "--method", method, path]
    for key, value in (fields or {}).items():
        args.extend(["-f", f"{key}={value}"])
    return run_gh(args)


def gh_api_json(method: str, path: str, payload: dict) -> dict:
    result = subprocess.run(
        ["gh", "api", "--method", method, path, "--input", "-"],
        check=True,
        capture_output=True,
        text=True,
        input=json.dumps(payload),
    )
    return json.loads(result.stdout)


def post_commit_status(
    repo: str,
    sha: str,
    state: str,
    context: str,
    description: str,
    target_url: str,
) -> None:
    gh_api(
        "POST",
        f"repos/{repo}/statuses/{sha}",
        {
            "state": state,
            "context": context,
            "description": description,
            "target_url": target_url,
        },
    )


def find_matching_pr(repo: str, issue_number: int) -> dict | None:
    output = run_gh(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "number,title,body,url,isDraft,headRefName,headRefOid",
        ]
    )
    prs = json.loads(output)
    fix_pattern = re.compile(rf"(?im)\bfixes\s+#\s*{issue_number}\b")
    ref_pattern = re.compile(rf"(?im)\bissue\s*#?\s*{issue_number}\b|#{issue_number}\b")

    matches: list[dict] = []
    for pr in prs:
        body = pr.get("body") or ""
        title = pr.get("title") or ""
        head = pr.get("headRefName") or ""
        if fix_pattern.search(body) or ref_pattern.search(body) or ref_pattern.search(title) or str(issue_number) in head:
            matches.append(pr)

    if not matches:
        return None
    matches.sort(key=lambda pr: pr["number"], reverse=True)
    return matches[0]


def get_pull_request(repo: str, pr_number: int) -> dict:
    output = run_gh(
        [
            "pr",
            "view",
            str(pr_number),
            "--repo",
            repo,
            "--json",
            "number,title,body,url,isDraft,headRefName,headRefOid",
        ]
    )
    return json.loads(output)


def jenkins_request(url: str, username: str, password: str, method: str = "GET") -> bytes:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read()


def trigger_jenkins(jenkins_base: str, job_name: str, username: str, password: str) -> None:
    job_path = urllib.parse.quote(job_name, safe="")
    jenkins_request(f"{jenkins_base}/job/{job_path}/build", username, password, method="POST")


def get_last_build(jenkins_base: str, job_name: str, username: str, password: str) -> dict:
    job_path = urllib.parse.quote(job_name, safe="")
    payload = jenkins_request(f"{jenkins_base}/job/{job_path}/lastBuild/api/json", username, password)
    return json.loads(payload)


def wait_for_build(
    jenkins_base: str,
    job_name: str,
    username: str,
    password: str,
    timeout_s: int,
    min_build_number: int,
) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        build = get_last_build(jenkins_base, job_name, username, password)
        if build.get("number", 0) >= min_build_number and not build.get("building"):
            return build
        time.sleep(2)
    raise TimeoutError("Timed out waiting for Jenkins build to finish")


def comment_on_pr(repo: str, pr_number: int, body: str) -> None:
    run_gh(["pr", "comment", str(pr_number), "--repo", repo, "--body", body])


def now_iso8601() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_check_run(
    repo: str,
    sha: str,
    name: str,
    description: str,
    target_url: str,
) -> int:
    payload = {
        "name": name,
        "head_sha": sha,
        "status": "in_progress",
        "details_url": target_url,
        "started_at": now_iso8601(),
        "output": {
            "title": name,
            "summary": description,
        },
    }
    response = gh_api_json("POST", f"repos/{repo}/check-runs", payload)
    return int(response["id"])


def update_check_run(
    repo: str,
    check_run_id: int,
    name: str,
    conclusion: str,
    summary: str,
    target_url: str,
) -> None:
    payload = {
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": now_iso8601(),
        "details_url": target_url,
        "output": {
            "title": name,
            "summary": summary,
        },
    }
    gh_api_json(
        "PATCH",
        f"repos/{repo}/check-runs/{check_run_id}",
        payload,
    )


def start_github_signal(
    repo: str,
    sha: str,
    name: str,
    description: str,
    target_url: str,
) -> tuple[str, int | None]:
    try:
        check_run_id = create_check_run(repo, sha, name, description, target_url)
        return ("check_run", check_run_id)
    except subprocess.CalledProcessError as exc:
        print(
            f"Check Run creation failed, falling back to commit status: {exc.stderr.strip() or exc}",
            file=sys.stderr,
            flush=True,
        )
        post_commit_status(repo, sha, "pending", name, description, target_url)
        return ("status", None)


def complete_github_signal(
    mode: str,
    repo: str,
    sha: str,
    name: str,
    signal_id: int | None,
    conclusion: str,
    summary: str,
    target_url: str,
) -> None:
    if mode == "check_run" and signal_id is not None:
        update_check_run(repo, signal_id, name, conclusion, summary, target_url)
        return

    status_state = "success" if conclusion == "success" else "failure"
    post_commit_status(repo, sha, status_state, name, summary.splitlines()[0], target_url)


def write_signal_file(path: str, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload), encoding="utf-8")


def read_signal_file(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Trigger Jenkins validation for an OpenHands PR")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPO", "rajshah4/openhands-sre"))
    parser.add_argument("--issue", type=int)
    parser.add_argument("--pr", type=int)
    parser.add_argument("--sha", help="Explicit PR head SHA. If omitted, fetched from GitHub.")
    parser.add_argument("--jenkins-url", default=os.getenv("JENKINS_URL", "http://127.0.0.1:8081"))
    parser.add_argument("--jenkins-job", default=os.getenv("JENKINS_JOB", "openhands-sre-demo"))
    parser.add_argument("--jenkins-user", default=os.getenv("JENKINS_USER", "admin"))
    parser.add_argument("--jenkins-password", default=os.getenv("JENKINS_PASSWORD", "admin"))
    parser.add_argument("--wait-timeout", type=int, default=1800)
    parser.add_argument("--build-timeout", type=int, default=900)
    parser.add_argument(
        "--check-name",
        default=os.getenv("JENKINS_CHECK_NAME", os.getenv("JENKINS_STATUS_CONTEXT", "Jenkins / OpenHands SRE Demo")),
    )
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--signal-file")
    parser.add_argument("--comment-pr", action="store_true")
    args = parser.parse_args()

    if bool(args.issue) == bool(args.pr):
        print("Pass exactly one of --issue or --pr", file=sys.stderr, flush=True)
        return 1

    if args.pr:
        pr = get_pull_request(args.repo, args.pr)
        print(f"Using PR #{pr['number']}: {pr['title']}", flush=True)
    else:
        print(f"Watching repo {args.repo} for an OpenHands PR linked to issue #{args.issue}...", flush=True)
        deadline = time.time() + args.wait_timeout
        pr = None
        while time.time() < deadline:
            pr = find_matching_pr(args.repo, args.issue)
            if pr:
                break
            time.sleep(15)

        if not pr:
            print(f"No matching PR found for issue #{args.issue} within {args.wait_timeout}s", file=sys.stderr, flush=True)
            return 1

    print(f"Found PR #{pr['number']}: {pr['title']}", flush=True)
    head_sha = args.sha or pr.get("headRefOid")
    if not head_sha:
        print(f"PR #{pr['number']} is missing a head SHA; cannot create a GitHub check run", file=sys.stderr, flush=True)
        return 1

    if args.signal_file and Path(args.signal_file).exists():
        signal = read_signal_file(args.signal_file)
        next_build_number = int(signal["next_build_number"])
        build_url = signal["build_url"]
        signal_mode = signal["signal_mode"]
        signal_id = signal.get("signal_id")
    else:
        previous_build = get_last_build(args.jenkins_url, args.jenkins_job, args.jenkins_user, args.jenkins_password)
        next_build_number = previous_build.get("number", 0) + 1
        build_url = f"{args.jenkins_url}/job/{urllib.parse.quote(args.jenkins_job, safe='')}/{next_build_number}/"
        signal_mode, signal_id = start_github_signal(
            args.repo,
            head_sha,
            args.check_name,
            f"Jenkins build #{next_build_number} is running",
            build_url,
        )
        if args.signal_file:
            write_signal_file(
                args.signal_file,
                {
                    "next_build_number": next_build_number,
                    "build_url": build_url,
                    "signal_mode": signal_mode,
                    "signal_id": signal_id,
                },
            )

    if args.prepare_only:
        print(f"Prepared GitHub signal for PR #{pr['number']} build #{next_build_number}", flush=True)
        return 0

    print(f"Triggering Jenkins job '{args.jenkins_job}' at {args.jenkins_url} ...", flush=True)
    try:
        trigger_jenkins(args.jenkins_url, args.jenkins_job, args.jenkins_user, args.jenkins_password)
        build = wait_for_build(
            args.jenkins_url,
            args.jenkins_job,
            args.jenkins_user,
            args.jenkins_password,
            args.build_timeout,
            next_build_number,
        )
    except Exception as exc:
        complete_github_signal(
            signal_mode,
            args.repo,
            head_sha,
            args.check_name,
            signal_id,
            "failure",
            f"Jenkins bridge failed before completion: {exc}",
            build_url,
        )
        raise

    result = build.get("result")
    build_url = build.get("url") or build_url
    conclusion = "success" if result == "SUCCESS" else "failure"
    summary = (
        f"Jenkins build #{build.get('number')} passed.\n\nJob: `{args.jenkins_job}`\nResult: `{result}`\nURL: {build_url}"
        if result == "SUCCESS"
        else f"Jenkins build #{build.get('number')} failed.\n\nJob: `{args.jenkins_job}`\nResult: `{result}`\nURL: {build_url}"
    )
    complete_github_signal(signal_mode, args.repo, head_sha, args.check_name, signal_id, conclusion, summary, build_url)
    print(f"Jenkins build #{build.get('number')} finished with result: {result}", flush=True)
    if build_url:
        print(build_url, flush=True)

    if args.comment_pr:
        body = (
            f"Jenkins demo validation completed.\n\n"
            f"- Job: `{args.jenkins_job}`\n"
            f"- Build: #{build.get('number')}\n"
            f"- Result: `{result}`\n"
            f"- URL: {build_url}"
        )
        comment_on_pr(args.repo, pr["number"], body)
        print(f"Commented on PR #{pr['number']} with Jenkins result.", flush=True)

    return 0 if result == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
