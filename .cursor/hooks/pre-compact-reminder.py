#!/usr/bin/env python3
"""
Hook: 上下文折叠前提醒用户确认决策草稿。
兼容 Cursor (preCompact) 和 Claude Code (PreCompact)。
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compat import HookIO


def main():
    hook = HookIO()
    project_root = hook.get_project_root()

    draft_path = os.path.join(project_root, ".teamwork", "drafts", "current.json")

    if not os.path.exists(draft_path):
        hook.user_message(
            "上下文即将折叠。当前没有决策草稿，如果对话中有重要的业务决策，请让 AI 先记录到草稿中。"
        )
        return

    mtime = os.path.getmtime(draft_path)
    minutes_ago = int((time.time() - mtime) / 60)

    try:
        with open(draft_path, "r", encoding="utf-8") as f:
            draft = json.load(f)
        entry_count = len(draft.get("entries", []))
    except (json.JSONDecodeError, OSError):
        entry_count = 0

    hook.user_message(
        f"上下文即将折叠。决策草稿包含 {entry_count} 条记录，"
        f"最后更新于 {minutes_ago} 分钟前。"
        f"请确认重要的业务决策已记录到草稿中。"
    )


if __name__ == "__main__":
    main()
