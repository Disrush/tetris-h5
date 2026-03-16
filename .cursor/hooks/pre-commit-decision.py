#!/usr/bin/env python3
"""
Hook: 提交前决策记录生成器。
兼容 Cursor (beforeShellExecution) 和 Claude Code (PreToolUse/Bash)。

拦截 git commit，要求 Agent 生成结构化的团队决策记录，
让用户审阅确认后保存到 .teamwork/decisions/，再允许提交。
通过 flag 文件机制避免二次拦截导致死循环。
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compat import HookIO

FLAG_DIR = "/tmp/cursor-hooks"


def resolve_current_user(hook, cwd):
    config_path = os.path.join(cwd, ".teamwork", "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}

    members = config.get("team_members", [])
    email_map = {m.get("email", "").lower(): m for m in members if m.get("email")}

    user_email = hook.get_user_email()
    if user_email and user_email.lower() in email_map:
        m = email_map[user_email.lower()]
        return {"name": m["name"], "role": m.get("role", ""), "email": user_email}

    try:
        git_email = subprocess.run(
            ["git", "config", "user.email"], cwd=cwd,
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if git_email and git_email.lower() in email_map:
            m = email_map[git_email.lower()]
            return {"name": m["name"], "role": m.get("role", ""), "email": git_email}
    except Exception:
        pass

    try:
        git_name = subprocess.run(
            ["git", "config", "user.name"], cwd=cwd,
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        name_map = {m["name"]: m for m in members}
        if git_name and git_name in name_map:
            m = name_map[git_name]
            return {"name": m["name"], "role": m.get("role", ""), "email": ""}
        if git_name:
            return {"name": git_name, "role": "", "email": ""}
    except Exception:
        pass

    if user_email:
        return {"name": user_email.split("@")[0], "role": "", "email": user_email}
    return {"name": "未知用户", "role": "", "email": ""}


def get_flag_path(conversation_id):
    os.makedirs(FLAG_DIR, exist_ok=True)
    return os.path.join(FLAG_DIR, f"decision-{conversation_id}")


def get_staged_diff(cwd):
    try:
        stat = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            cwd=cwd, capture_output=True, text=True, timeout=10
        ).stdout.strip()

        detail = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=cwd, capture_output=True, text=True, timeout=10
        ).stdout.strip()

        return stat, detail
    except Exception:
        return "", ""


def should_skip(command):
    skip_flags = ["--amend", "[skip decision]", "[no decision]", "merge"]
    return any(flag in command for flag in skip_flags)


def check_draft_exists(cwd):
    draft_path = os.path.join(cwd, ".teamwork", "drafts", "current.json")
    if os.path.exists(draft_path):
        try:
            with open(draft_path, "r", encoding="utf-8") as f:
                draft = json.load(f)
            count = len(draft.get("entries", []))
            return f"已有决策草稿，包含 {count} 条 entry。" if count > 0 else ""
        except (json.JSONDecodeError, OSError):
            pass
    return ""


def list_existing_keys(cwd):
    decisions_dir = os.path.join(cwd, ".teamwork", "decisions")
    if not os.path.isdir(decisions_dir):
        return "（暂无已有决策记录）"

    keys = set()
    for fname in os.listdir(decisions_dir):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(decisions_dir, fname), "r", encoding="utf-8") as f:
                rec = json.load(f)
            for entry in rec.get("entries", []):
                k = entry.get("decision_key")
                if k:
                    keys.add(k)
        except (json.JSONDecodeError, OSError):
            continue

    if not keys:
        return "（暂无已有决策记录）"
    return "已有 decision_key 列表：" + ", ".join(sorted(keys))


def ensure_teamwork_dir(cwd):
    for d in [".teamwork", ".teamwork/decisions", ".teamwork/drafts"]:
        os.makedirs(os.path.join(cwd, d), exist_ok=True)
    config_path = os.path.join(cwd, ".teamwork", "config.json")
    if not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "team_members": [], "major_change_keywords": []}, f, ensure_ascii=False, indent=2)


def main():
    hook = HookIO()
    command = hook.get_command()
    cwd = hook.get_cwd()
    conversation_id = hook.get_conversation_id()

    if "git commit" not in command or should_skip(command):
        hook.allow()
        return

    flag_path = get_flag_path(conversation_id)

    if os.path.exists(flag_path):
        try:
            os.remove(flag_path)
        except OSError:
            pass
        hook.allow()
        return

    diff_stat, diff_detail = get_staged_diff(cwd)

    if not diff_stat:
        hook.allow()
        return

    ensure_teamwork_dir(cwd)

    with open(flag_path, "w") as f:
        f.write(conversation_id)

    max_len = 3000
    diff_preview = diff_detail[:max_len]
    if len(diff_detail) > max_len:
        diff_preview += "\n... (diff 已截断)"

    draft_hint = check_draft_exists(cwd)
    existing_keys = list_existing_keys(cwd)

    user = resolve_current_user(hook, cwd)
    user_line = f"**当前用户：{user['name']}（{user['role'] or '角色未配置'}）**"
    if user['email']:
        user_line += f"  email: {user['email']}"

    agent_msg = (
        "⚠️ Git commit 已被 hook 拦截，请生成团队决策记录。\n\n"
        f"👤 {user_line}\n"
        "请在决策记录的 author 字段直接使用以上用户信息。\n\n"
        "请按以下步骤操作：\n\n"
        f"{'📋 ' + draft_hint + ' 请以草稿为基础进行增补。' if draft_hint else '📋 无现有草稿，请从对话内容提取。'}\n\n"
        "1. **回顾本次对话**，识别有明确业务意图的功能变更。\n\n"
        "2. **分析暂存区变更**：\n\n"
        f"【变更统计】\n{diff_stat}\n\n"
        f"【变更详情】\n{diff_preview}\n\n"
        "3. **检查已有决策记录**，判断 decision_key 是否需要复用：\n"
        f"   {existing_keys}\n\n"
        "4. **生成决策记录 JSON 文件**，保存到 `.teamwork/decisions/` 目录。\n"
        "   文件名格式：`{YYYY-MM-DDTHHMM}_{author}_{commit_hash前6位}.json`\n\n"
        "   每条 entry 必须包含：\n"
        "   - `decision_key`：简短英文 kebab-case 标识（同一件事复用已有 key）\n"
        "   - `requirement.what` / `requirement.why`：业务需求（不含代码实现细节）\n"
        "   - `solution.approach` / `solution.not_included`：解决方案（非代码层面）\n"
        "   - `decision.type`：`human`（用户明确要求） / `human_ai`（协商达成） / `ai`（AI 自主决定）\n"
        "   - `decision.motivation`：为什么选这个方案\n"
        "   - 如果复用已有 key，加 `supersedes` 字段引用旧记录\n\n"
        "   根据变更内容判断 `is_major_change`（新增模块/删除功能/数据结构变更/API 变更）。\n"
        "   如果是大变更，`change_background` 必须填写。\n\n"
        "⚠️ **以下类型的改动不要记录为 entry**：\n"
        "   - AI 理解偏差纠正、需求沟通偏差的回退\n"
        "   - 代码 bug/类型错误/逻辑错误修复\n"
        "   - 纯重构、格式化等非功能性改动\n"
        "   将这些归入 `noise_excluded` 字段说明。\n\n"
        "   如果 **所有改动都属于应排除的类型**，无需生成决策文件，\n"
        "   直接在 commit 消息中加 `[skip decision]` 标记后重新 commit。\n\n"
        "5. **呈现给用户审阅**：展示生成的决策记录内容，等待用户确认或修改。\n\n"
        "6. 用户确认后：\n"
        "   - 保存 JSON 文件到 `.teamwork/decisions/`\n"
        "   - 如果存在 `.teamwork/drafts/current.json`，删除它\n"
        "   - 执行 `git add .teamwork/decisions/`\n"
        f"   - 重新执行原 commit 命令：`{command}`"
    )

    hook.deny(
        user_message="Hook: 请先生成团队决策记录再提交...",
        agent_message=agent_msg
    )


if __name__ == "__main__":
    main()
