#!/usr/bin/env python3
"""
Hook: Pull 后呈现团队变更。
兼容 Cursor (postToolUse/Shell) 和 Claude Code (PostToolUse/Bash)。

在 git pull 完成后，读取新增的决策记录文件，
按重要度排序后格式化为分层文本，注入对话上下文。
"""

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compat import HookIO


def is_git_pull(hook):
    command = hook.get_command()
    if not command:
        tool_input = hook.payload.get("tool_input", {})
        if isinstance(tool_input, str):
            command = tool_input
        elif isinstance(tool_input, dict):
            command = tool_input.get("command", "")
    return bool(re.match(r"^git\s+pull", command.strip()))


def get_new_decision_files(cwd):
    try:
        result = subprocess.run(
            ["git", "log", "ORIG_HEAD..HEAD", "--name-only", "--pretty=format:"],
            cwd=cwd, capture_output=True, text=True, timeout=10
        )
        files = [
            f.strip() for f in result.stdout.strip().split("\n")
            if f.strip() and f.strip().startswith(".teamwork/decisions/") and f.strip().endswith(".json")
        ]
        return list(set(files))
    except Exception:
        return []


def load_decision_file(cwd, rel_path):
    fpath = os.path.join(cwd, rel_path)
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return {}


def format_review(records):
    if not records:
        return ""

    major = []
    normal = []

    type_labels = {"human": "👤 人工决策", "human_ai": "👥 人+AI共同决策", "ai": "🤖 AI决策"}

    for rec in records:
        author = rec.get("author", {})
        for entry in rec.get("entries", []):
            item = {
                "author_name": author.get("name", "?"),
                "author_role": author.get("role", "?"),
                "timestamp": rec.get("timestamp", "?")[:16],
                "requirement_what": entry.get("requirement", {}).get("what", ""),
                "solution_approach": entry.get("solution", {}).get("approach", ""),
                "decision_type": type_labels.get(entry.get("decision", {}).get("type", ""), ""),
                "motivation": entry.get("decision", {}).get("motivation", ""),
                "background": rec.get("change_background", ""),
                "supersedes": entry.get("supersedes"),
                "is_major": rec.get("is_major_change", False),
                "raw_type": entry.get("decision", {}).get("type", "ai"),
            }
            if item["is_major"]:
                major.append(item)
            else:
                normal.append(item)

    type_order = {"human": 0, "human_ai": 1, "ai": 2}
    major.sort(key=lambda x: type_order.get(x["raw_type"], 9))
    normal.sort(key=lambda x: type_order.get(x["raw_type"], 9))

    lines = ["## 团队变更通报（自你上次 pull 以来）\n"]

    if major:
        lines.append(f"### 🔴 重大变更（{len(major)} 条）")
        for i, item in enumerate(major, 1):
            lines.append(
                f"{i}. [{item['author_name']} / {item['author_role']}] {item['timestamp']}\n"
                f"   需求：{item['requirement_what']}\n"
                f"   方案：{item['solution_approach']}\n"
                f"   决策类型：{item['decision_type']}\n"
                f"   动机：{item['motivation']}"
            )
            if item["background"]:
                lines.append(f"   背景：{item['background']}")
            if item["supersedes"]:
                lines.append(f"   ↳ 替代了之前的决策（{item['supersedes'].get('reason', '')}）")
            lines.append("")

    if normal:
        lines.append(f"### 🟡 一般变更（{len(normal)} 条）")
        offset = len(major)
        for i, item in enumerate(normal, offset + 1):
            lines.append(
                f"{i}. [{item['author_name']} / {item['author_role']}] {item['timestamp']}\n"
                f"   需求：{item['requirement_what']}\n"
                f"   方案：{item['solution_approach']}\n"
                f"   决策类型：{item['decision_type']}"
            )
            if item["supersedes"]:
                lines.append(f"   ↳ 替代了之前的决策（{item['supersedes'].get('reason', '')}）")
            lines.append("")

    human_decisions = [
        item for item in (major + normal) if item["raw_type"] == "human"
    ]
    if human_decisions:
        lines.append("### ⚠️ 决策提醒")
        for item in human_decisions:
            lines.append(
                f"- {item['author_name']} 明确决定了「{item['requirement_what']}」，"
                f"修改此功能需先与其沟通"
            )

    return "\n".join(lines)


def main():
    hook = HookIO()

    if not is_git_pull(hook):
        hook.empty()
        return

    project_root = hook.get_project_root()
    new_files = get_new_decision_files(project_root)

    if not new_files:
        hook.empty()
        return

    records = []
    for f in new_files:
        rec = load_decision_file(project_root, f)
        if rec:
            records.append(rec)

    records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    review_text = format_review(records)

    if review_text:
        hook.additional_context(review_text)
    else:
        hook.empty()


if __name__ == "__main__":
    main()
