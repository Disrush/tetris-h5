#!/usr/bin/env python3
"""
Hook: 会话启动时注入团队决策上下文。
兼容 Cursor (sessionStart) 和 Claude Code (SessionStart)。
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compat import HookIO


def resolve_current_user(hook, config, project_root):
    members = config.get("team_members", [])
    email_map = {m.get("email", "").lower(): m for m in members if m.get("email")}

    user_email = hook.get_user_email()
    if user_email and user_email.lower() in email_map:
        m = email_map[user_email.lower()]
        return {"name": m["name"], "role": m.get("role", ""), "email": user_email, "source": "account"}

    try:
        git_email = subprocess.run(
            ["git", "config", "user.email"],
            cwd=project_root, capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if git_email and git_email.lower() in email_map:
            m = email_map[git_email.lower()]
            return {"name": m["name"], "role": m.get("role", ""), "email": git_email, "source": "git_email"}
    except Exception:
        pass

    try:
        git_name = subprocess.run(
            ["git", "config", "user.name"],
            cwd=project_root, capture_output=True, text=True, timeout=5
        ).stdout.strip()
        name_map = {m["name"]: m for m in members}
        if git_name and git_name in name_map:
            m = name_map[git_name]
            return {"name": m["name"], "role": m.get("role", ""), "email": "", "source": "git_name"}
        if git_name:
            return {"name": git_name, "role": "", "email": "", "source": "git_name_unmatched"}
    except Exception:
        pass

    if user_email:
        return {"name": user_email.split("@")[0], "role": "", "email": user_email, "source": "email_fallback"}

    return {"name": "未知用户", "role": "", "email": "", "source": "unknown"}


def load_config(project_root):
    config_path = os.path.join(project_root, ".teamwork", "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_decisions(project_root):
    decisions_dir = os.path.join(project_root, ".teamwork", "decisions")
    if not os.path.isdir(decisions_dir):
        return []

    records = []
    for fname in os.listdir(decisions_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(decisions_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                records.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue

    records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return records


def get_active_decisions(records):
    superseded_ids = set()
    for rec in records:
        for entry in rec.get("entries", []):
            sup = entry.get("supersedes", {})
            if sup.get("record_id"):
                superseded_ids.add(sup["record_id"])

    active = {}
    for rec in records:
        if rec.get("id") in superseded_ids:
            continue
        for entry in rec.get("entries", []):
            key = entry.get("decision_key", "")
            if key and key not in active and entry.get("status") != "deprecated":
                active[key] = {**entry, "_record": rec}

    return active


def format_context(active, config, current_user):
    lines = ["## 团队决策上下文\n"]

    lines.append(f"**当前用户：{current_user['name']}（{current_user.get('role') or '角色未配置'}）**\n")

    members = {m["name"]: m["role"] for m in config.get("team_members", [])}
    lines.append(f"团队成员：{', '.join(f'{n}({r})' for n, r in members.items()) if members else '未配置'}\n")

    if not active:
        return "\n".join(lines)

    lines.append(f"当前 active 决策共 {len(active)} 条：\n")

    type_labels = {"human": "👤人工", "human_ai": "👥人+AI", "ai": "🤖AI"}

    for i, (key, entry) in enumerate(active.items(), 1):
        rec = entry["_record"]
        author = rec.get("author", {})
        decision = entry.get("decision", {})
        req = entry.get("requirement", {})

        label = type_labels.get(decision.get("type", ""), "")
        lines.append(
            f"{i}. [{author.get('name', '?')}/{author.get('role', '?')}] "
            f"{rec.get('timestamp', '?')[:10]}\n"
            f"   decision_key: {key}\n"
            f"   需求：{req.get('what', '')}\n"
            f"   决策类型：{label}\n"
        )

    return "\n".join(lines)


def main():
    hook = HookIO()
    project_root = hook.get_project_root()

    config = load_config(project_root)
    current_user = resolve_current_user(hook, config, project_root)
    records = load_decisions(project_root)
    active = get_active_decisions(records[:10])
    context = format_context(active, config, current_user)

    env = {"TEAMWORK_DIR": ".teamwork", "TEAMWORK_USER": current_user["name"]}
    hook.context(text=context, env=env)


if __name__ == "__main__":
    main()
