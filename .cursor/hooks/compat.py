"""
Cursor / Claude Code 双平台 Hook 兼容层。

平台检测：通过输入 JSON 中的 cursor_version 字段或 CURSOR_VERSION 环境变量判断。
提供统一的输入读取、命令提取、输出格式化接口。
"""

import json
import os
import sys


class HookIO:
    def __init__(self):
        self.payload = json.load(sys.stdin)
        self.platform = self._detect_platform()

    def _detect_platform(self):
        if self.payload.get("cursor_version") or os.environ.get("CURSOR_VERSION"):
            return "cursor"
        return "claude_code"

    @property
    def is_cursor(self):
        return self.platform == "cursor"

    @property
    def is_claude_code(self):
        return self.platform == "claude_code"

    def get_command(self):
        if self.is_cursor:
            if "command" in self.payload:
                return self.payload["command"]
        tool_input = self.payload.get("tool_input", {})
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except json.JSONDecodeError:
                return tool_input
        if isinstance(tool_input, dict):
            return tool_input.get("command", self.payload.get("command", ""))
        return ""

    def get_cwd(self):
        return (
            self.payload.get("cwd")
            or os.environ.get("CURSOR_PROJECT_DIR")
            or os.environ.get("CLAUDE_PROJECT_DIR")
            or "."
        )

    def get_project_root(self):
        roots = self.payload.get("workspace_roots", [])
        if roots:
            return roots[0]
        return (
            os.environ.get("CURSOR_PROJECT_DIR")
            or os.environ.get("CLAUDE_PROJECT_DIR")
            or self.payload.get("cwd", ".")
        )

    def get_conversation_id(self):
        return (
            self.payload.get("conversation_id")
            or self.payload.get("session_id")
            or "unknown"
        )

    def get_user_email(self):
        return (
            self.payload.get("user_email")
            or os.environ.get("CURSOR_USER_EMAIL")
            or ""
        )

    def allow(self):
        if self.is_cursor:
            json.dump({"permission": "allow"}, sys.stdout)

    def deny(self, user_message="", agent_message=""):
        if self.is_cursor:
            result = {"permission": "deny"}
            if user_message:
                result["user_message"] = user_message
            if agent_message:
                result["agent_message"] = agent_message
            json.dump(result, sys.stdout, ensure_ascii=False)
        else:
            reason = agent_message or user_message
            if reason:
                print(reason, file=sys.stderr)
            sys.exit(2)

    def context(self, text="", env=None):
        """SessionStart: inject context and env vars."""
        if self.is_cursor:
            result = {}
            if env:
                result["env"] = env
            if text:
                result["additional_context"] = text
            json.dump(result, sys.stdout, ensure_ascii=False)
        else:
            if text:
                print(text)

    def additional_context(self, text=""):
        """PostToolUse: inject additional context."""
        if self.is_cursor:
            if text:
                json.dump({"additional_context": text}, sys.stdout, ensure_ascii=False)
            else:
                json.dump({}, sys.stdout)
        else:
            if text:
                print(text)

    def user_message(self, text=""):
        """PreCompact: show message to user."""
        if self.is_cursor:
            json.dump({"user_message": text}, sys.stdout, ensure_ascii=False)
        else:
            if text:
                print(text)

    def empty(self):
        if self.is_cursor:
            json.dump({}, sys.stdout)
