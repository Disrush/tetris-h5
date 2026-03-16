# TeamVibe

**Decision version control for team vibe coding.**

> Multi-agent tools are everywhere. Multi-human collaboration tools for vibe coding teams? None — until now.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[中文版](#中文版)

---

## The Problem

When multiple team members (PMs, designers, developers) use AI coding assistants (Cursor, Claude Code, etc.) on the same project, chaos emerges:

| # | Problem | Impact |
|---|---------|--------|
| 1 | **Business decisions are scattered** across individual AI chat sessions — impossible to trace | Team misalignment |
| 2 | **No distinction** between human-explicit decisions and AI-autonomous decisions | Silent conflicts |
| 3 | **Major changes lack context** — other members can't understand *why* something changed | Wasted investigation time |
| 4 | **After pulling code**, no idea what business decisions others made | Blind collaboration |
| 5 | **Accidental overrides** of another member's deliberate decisions | Lost work & trust |
| 6 | **AI context window compaction** loses early-session decisions | Decision amnesia |

**Existing tools solve multi-agent orchestration.** TeamVibe solves **multi-human + multi-AI team collaboration** — the actual bottleneck in vibe coding teams.

## How It Works

TeamVibe is a **pure Git-based, zero-infrastructure** decision version control system. It runs entirely through your IDE's hooks and rules — no servers, no databases, no SaaS.

```
┌─────────────────────────────────────────────────────┐
│                    TeamVibe Architecture             │
│                                                     │
│  ┌─── Rules Layer ───┐    ┌─── Hooks Layer ───┐     │
│  │ Conflict detection │    │ Commit gate       │     │
│  │ Draft maintenance  │    │ Push validation   │     │
│  │ (AI-driven)        │    │ Pull briefing     │     │
│  └────────────────────┘    │ Session init      │     │
│                            │ Compact reminder  │     │
│                            └───────────────────┘     │
│                                                      │
│  ┌─── Data Layer (.teamwork/) ──────────────────┐    │
│  │ decisions/*.json  — versioned decision chain  │    │
│  │ config.json       — team member registry      │    │
│  │ drafts/           — real-time decision drafts  │   │
│  └───────────────────────────────────────────────┘   │
│                                                      │
│              Distributed via Git — no server needed   │
└─────────────────────────────────────────────────────┘
```

### Core Concepts

**Decision Records, not Changelogs.** TeamVibe tracks *business decisions* (what, why, who decided), not code diffs. Each commit generates a structured JSON decision record reviewed by the author before committing.

**Decision Chain via `supersedes`.** Same business topic uses the same `decision_key`. New decisions reference old ones through `supersedes` — append-only, no merge conflicts.

**Three Decision Types:**

| Type | Meaning | Conflict behavior |
|------|---------|-------------------|
| `human` | Explicit human decision | **Must** discuss offline before overriding |
| `human_ai` | Human-AI consensus | Warn, current user decides |
| `ai` | AI autonomous decision | Mention briefly, proceed |

### Workflow

```
During conversation:
  AI maintains decision drafts in real-time (Rule-driven)
         │
         ▼
git commit → Hook intercepts → AI generates decision record
         → User reviews → Record saved → Commit proceeds
         │
         ▼
git push  → Hook validates completeness → Push proceeds
         │
         ▼
git pull  → Hook reads new decisions → Team briefing injected
```

## Supported Platforms

| Platform | Hooks Config | Rules |
|----------|-------------|-------|
| **Cursor** | `.cursor/hooks.json` | `.cursor/rules/teamwork-decisions.mdc` |
| **Claude Code** | `.claude/settings.json` | `.claude/rules/teamwork-decisions.md` |

Both platforms share the **same hook scripts** (`.cursor/hooks/*.py`) through a compatibility layer that auto-detects the runtime environment.

## Quick Start

### 1. Add to your project

Copy these directories into your project root:

```
.cursor/          # Cursor hooks & rules
.claude/          # Claude Code hooks & rules
.teamwork/        # Decision data (auto-created on first commit)
```

### 2. Configure your team

Create `.teamwork/config.json`:

```json
{
  "version": "1.0",
  "team_members": [
    { "name": "Alice", "role": "Product Manager", "email": "alice@team.com" },
    { "name": "Bob", "role": "Frontend Engineer", "email": "bob@team.com" }
  ]
}
```

### 3. Start coding

That's it. The hooks and rules activate automatically:

- **Start a session** → Team decisions injected as context
- **Make changes** → AI detects conflicts with existing decisions
- **Commit** → Decision record generated and reviewed
- **Push** → Completeness validated
- **Pull** → Team change briefing displayed

## Demo: Tetris H5

This repo includes a [Tetris H5 game](tetris.html) as a working demo. Two team members collaborate on the game using vibe coding:

```
Alice: "Change all blocks to rounded corners"
  → Decision record: block-rounded-corners (human)

Bob: "Remove the Z-shaped block"
  → Decision record: remove-z-block (human)

Alice: "Restore Z block, remove L block instead"
  → Conflict detected! Bob's human decision on Z block.
  → Alice confirms offline discussion with Bob.
  → New record supersedes Bob's, with resolution noted.
```

See `.teamwork/decisions/` for real decision records generated during development.

## Decision Record Format

```json
{
  "id": "2026-03-16T1430_alice_a1b2c3",
  "author": { "name": "Alice", "role": "Product Manager" },
  "timestamp": "2026-03-16T14:30:00Z",
  "is_major_change": true,
  "change_background": "User feedback on large CSV imports",
  "entries": [
    {
      "decision_key": "csv-import-progress",
      "status": "active",
      "requirement": { "what": "Progress display for CSV import", "why": "Users have no visibility during large imports" },
      "solution": { "approach": "Streaming parser + progress bar", "not_included": "No speed optimization" },
      "decision": { "type": "human", "motivation": "PM explicitly required progress bar", "decided_by": "Alice" }
    }
  ]
}
```

## File Structure

```
project-root/
├── .cursor/
│   ├── hooks.json                    # Cursor hooks config
│   ├── hooks/
│   │   ├── compat.py                 # Cross-platform compatibility layer
│   │   ├── session-init.py           # Session start: inject team context
│   │   ├── pre-commit-decision.py    # Commit gate: generate decision record
│   │   ├── pre-push-validate.py      # Push gate: validate completeness
│   │   ├── post-pull-review.py       # Pull briefing: show team changes
│   │   └── pre-compact-reminder.py   # Context compaction reminder
│   └── rules/
│       └── teamwork-decisions.mdc    # AI behavior rules (Cursor)
├── .claude/
│   ├── settings.json                 # Claude Code hooks config
│   └── rules/
│       └── teamwork-decisions.md     # AI behavior rules (Claude Code)
├── .teamwork/
│   ├── config.json                   # Team configuration
│   ├── decisions/                    # Decision records (Git-tracked)
│   └── drafts/                       # Work-in-progress drafts (gitignored)
```

## Why Not Just Use...

| Approach | Limitation |
|----------|-----------|
| Git commit messages | No structure, no conflict detection, no decision attribution |
| PR descriptions | Too late — decisions are already made during vibe coding |
| Notion / Confluence | Disconnected from code, manual sync, not in AI context |
| ADR (Architecture Decision Records) | Manual process, no automation, no real-time conflict detection |
| Multi-agent frameworks (CrewAI, AutoGen...) | Solve agent orchestration, not human team coordination |

## Contributing

Contributions welcome! Areas of interest:

- Support for additional AI coding tools (Windsurf, Copilot, etc.)
- Web dashboard for decision visualization
- Decision analytics and team insights
- Internationalization

## License

MIT

---

# 中文版

# TeamVibe

**团队 Vibe Coding 的决策版本管理工具。**

> 多 Agent 协作工具遍地都是。但多人 + 多 AI 的 Vibe Coding 团队协作工具？没有 —— 直到现在。

## 解决什么问题

当多个团队成员（产品经理、设计师、开发工程师）同时使用 AI 编程助手（Cursor、Claude Code 等）在同一项目上进行 vibe coding 时，混乱随之而来：

| # | 问题 | 影响 |
|---|------|------|
| 1 | **业务决策散落在各自的 AI 对话中**，无法追溯 | 团队认知不对齐 |
| 2 | **无法区分**人工明确决策和 AI 自主决策 | 静默冲突 |
| 3 | **大的需求变更缺乏背景说明**，其他成员无法理解变更动机 | 浪费排查时间 |
| 4 | **Pull 代码后**不知道其他人做了什么业务变更 | 盲人协作 |
| 5 | **无意中推翻**其他成员深思熟虑的决策 | 信任崩塌 |
| 6 | **AI 上下文窗口折叠后**，对话早期的决策信息丢失 | 决策失忆 |

**现有工具解决的是多 Agent 编排。** TeamVibe 解决的是**多人 + 多 AI 团队协作** —— 这才是 vibe coding 团队的真正瓶颈。

## 工作原理

TeamVibe 是一套**纯 Git 分发、零基础设施**的决策版本管理系统。完全通过 IDE 的 Hooks 和 Rules 运行 —— 不需要服务器、数据库或 SaaS 服务。

### 核心概念

**管理的不是代码变更，而是业务决策链路。** 每次提交时生成结构化的 JSON 决策记录，由作者审阅确认后才允许提交。

**决策版本链（`supersedes` 机制）：** 同一业务话题使用相同的 `decision_key`。新决策通过 `supersedes` 引用旧决策 —— 纯追加式，不会产生 Git 合并冲突。

**三种决策类型：**

| 类型 | 含义 | 冲突处理 |
|------|------|---------|
| `human` | 人工明确决策 | **必须**线下沟通后才能推翻 |
| `human_ai` | 人 + AI 共同达成 | 提醒，当前用户自行判断 |
| `ai` | AI 自主决策 | 简要提及，直接执行 |

### 工作流

```
对话过程中：
  AI 实时维护决策草稿（Rule 驱动）
         │
         ▼
git commit → Hook 拦截 → AI 生成决策记录
         → 用户审阅 → 记录保存 → 提交放行
         │
         ▼
git push  → Hook 校验完整性 → 推送放行
         │
         ▼
git pull  → Hook 读取新决策 → 团队变更通报注入对话
```

## 支持的平台

| 平台 | Hooks 配置 | Rules |
|------|-----------|-------|
| **Cursor** | `.cursor/hooks.json` | `.cursor/rules/teamwork-decisions.mdc` |
| **Claude Code** | `.claude/settings.json` | `.claude/rules/teamwork-decisions.md` |

两个平台共享**同一套 hook 脚本**（`.cursor/hooks/*.py`），通过兼容层自动检测运行环境。

## 快速开始

### 1. 添加到你的项目

将以下目录复制到项目根目录：

```
.cursor/          # Cursor hooks 和 rules
.claude/          # Claude Code hooks 和 rules
.teamwork/        # 决策数据（首次 commit 时自动创建）
```

### 2. 配置团队

创建 `.teamwork/config.json`：

```json
{
  "version": "1.0",
  "team_members": [
    { "name": "Alice", "role": "产品经理", "email": "alice@team.com" },
    { "name": "Bob", "role": "前端工程师", "email": "bob@team.com" }
  ]
}
```

### 3. 开始编码

搞定了。Hooks 和 Rules 自动生效：

- **启动会话** → 团队决策上下文自动注入
- **修改代码** → AI 自动检测与现有决策的冲突
- **提交** → 生成决策记录并审阅
- **推送** → 校验决策记录完整性
- **拉取** → 显示团队变更通报

## 演示：俄罗斯方块 H5

本仓库包含一个[俄罗斯方块 H5 游戏](tetris.html)作为实际协作演示。两位团队成员通过 vibe coding 协作开发这个游戏：

```
蒋延平："将方块全部改为圆角"
  → 决策记录：block-rounded-corners（human 类型）

amybriggs5010："移除 Z 形方块"
  → 决策记录：remove-z-block（human 类型）

蒋延平："恢复 Z 方块，去除 L 方块"
  → 检测到冲突！amybriggs5010 对 Z 方块有 human 类型决策。
  → 蒋延平确认已线下沟通。
  → 新记录 supersedes 旧记录，附带沟通结论。
```

查看 `.teamwork/decisions/` 目录可以看到开发过程中生成的真实决策记录。

## 为什么不用...

| 方案 | 局限性 |
|------|--------|
| Git commit message | 无结构、无冲突检测、无决策归属 |
| PR 描述 | 太晚了 —— vibe coding 时决策已经做完了 |
| Notion / Confluence | 与代码脱节，手动同步，不在 AI 上下文中 |
| ADR（架构决策记录） | 纯手动流程，无自动化，无实时冲突检测 |
| 多 Agent 框架（CrewAI、AutoGen...） | 解决 Agent 编排，不解决人类团队协调 |

## 参与贡献

欢迎贡献！感兴趣的方向：

- 支持更多 AI 编程工具（Windsurf、Copilot 等）
- 决策可视化 Web 面板
- 决策分析与团队洞察
- 国际化支持

## 许可证

MIT
