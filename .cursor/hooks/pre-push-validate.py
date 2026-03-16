#!/usr/bin/env python3
"""
Hook: 推送前校验决策记录完整性。
兼容 Cursor (beforeShellExecution) 和 Claude Code (PreToolUse/Bash)。

检查待推送的 commit 中：
1. 非 [skip decision] 的 commit 是否有对应的决策记录文件变更
2. 标记为 is_major_change 的记录是否填写了 change_background
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compat import HookIO


def get_unpushed_commits(cwd):
    for ref in ["origin/HEAD..HEAD", "@{u}..HEAD"]:
        try:
            result = subprocess.run(
                ["git", "log", "--format=%H %s", ref],
                cwd=cwd, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                commits = []
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        parts = line.split(" ", 1)
                        commits.append((parts[0], parts[1] if len(parts) > 1 else ""))
                return commits
        except Exception:
            continue
    return []


def get_commit_files(cwd, commit_hash):
    try:
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "-r", "--name-only", commit_hash],
            cwd=cwd, capture_output=True, text=True, timeout=10
        )
        return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except Exception:
        return []


def check_decisions(cwd, commits):
    issues = []

    for commit_hash, message in commits:
        if "[skip decision]" in message or "[no decision]" in message:
            continue
        if message.startswith("Merge"):
            continue

        files = get_commit_files(cwd, commit_hash)
        has_code_changes = any(
            not f.startswith(".teamwork/") and not f.startswith(".cursor/") and not f.startswith(".claude/")
            for f in files
        )
        has_decision_file = any(
            f.startswith(".teamwork/decisions/") and f.endswith(".json")
            for f in files
        )

        if has_code_changes and not has_decision_file:
            short_hash = commit_hash[:7]
            issues.append(
                f"Commit {short_hash}「{message}」包含代码变更但没有对应的决策记录文件"
            )

    decisions_dir = os.path.join(cwd, ".teamwork", "decisions")
    if os.path.isdir(decisions_dir):
        for fname in os.listdir(decisions_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(decisions_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    rec = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            if rec.get("is_major_change") and not rec.get("change_background", "").strip():
                issues.append(
                    f"决策记录 {fname} 标记为重大变更，但缺少 change_background（变更背景说明）"
                )

    return issues


def main():
    hook = HookIO()
    command = hook.get_command()
    cwd = hook.get_cwd()

    if "git push" not in command:
        hook.allow()
        return

    commits = get_unpushed_commits(cwd)
    if not commits:
        hook.allow()
        return

    issues = check_decisions(cwd, commits)

    if issues:
        issue_text = "\n".join(f"  - {issue}" for issue in issues)
        hook.deny(
            user_message="推送被拦截：决策记录不完整，请补充后再推送",
            agent_message=(
                "⚠️ Git push 被拦截，决策记录校验未通过：\n\n"
                f"{issue_text}\n\n"
                "请修复以上问题后重新推送：\n"
                "- 缺少决策记录的 commit：请生成决策记录文件后 amend 或新增 commit\n"
                "- 大变更缺少背景：请补充 change_background 字段"
            )
        )
        return

    hook.allow()


if __name__ == "__main__":
    main()
