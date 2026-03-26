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
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compat import HookIO, resolve_current_user


def resolve_current_user_simple(hook, cwd):
    """Wrapper that returns only the user dict (for backward compat)."""
    user, _ = resolve_current_user(hook, cwd)
    return user

FLAG_DIR = "/tmp/cursor-hooks"
FLAG_TTL_SECONDS = 600


def write_flag(flag_path):
    with open(flag_path, "w", encoding="utf-8") as f:
        f.write(str(time.time()))


def is_flag_valid(flag_path):
    try:
        with open(flag_path, "r", encoding="utf-8") as f:
            created_at = float(f.read().strip())
    except (OSError, ValueError):
        return False
    return time.time() - created_at < FLAG_TTL_SECONDS


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
    user = resolve_current_user_simple(hook, cwd)

    if user.get("source") in {"unregistered", "unknown"}:
        try:
            os.remove(flag_path)
        except OSError:
            pass
        hook.deny(
            user_message="Hook: 请先完成团队成员注册...",
            agent_message=(
                "⚠️ 当前用户尚未注册到项目团队配置中，暂不能提交。\n\n"
                f"检测到的身份：name={user.get('name') or 'not set'}, email={user.get('email') or 'not set'}\n"
                "请先告诉我你的显示名和团队角色，我会帮你写入 .teamwork/config.json。\n"
                "完成注册并提交配置后，再重新执行当前 commit。"
            )
        )
        return

    if os.path.exists(flag_path):
        if is_flag_valid(flag_path):
            try:
                os.remove(flag_path)
            except OSError:
                pass
            hook.allow()
            return
        try:
            os.remove(flag_path)
        except OSError:
            pass

    diff_stat, diff_detail = get_staged_diff(cwd)

    if not diff_stat:
        hook.allow()
        return

    ensure_teamwork_dir(cwd)

    write_flag(flag_path)

    max_len = 3000
    diff_preview = diff_detail[:max_len]
    if len(diff_detail) > max_len:
        diff_preview += "\n... (diff 已截断)"

    draft_hint = check_draft_exists(cwd)
    existing_keys = list_existing_keys(cwd)

    user = resolve_current_user_simple(hook, cwd)
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
        "   - 如果复用已有 key（即替代旧决策），**在该 entry 内**加 `supersedes` 字段：\n"
        "     ```json\n"
        "     \"supersedes\": { \"record_id\": \"旧记录ID\", \"reason\": \"替代原因\" }\n"
        "     ```\n"
        "     注意：supersedes 写在 entry 级别，不要写在 record 顶层。\n"
        "     只替代旧记录中同一 decision_key 的 entry，不影响旧记录中的其他 entry。\n\n"
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
