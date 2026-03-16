# 团队协作决策管理

你正在一个多人协作的 vibe coding 项目中工作。

## 一、冲突检测（每次用户描述需求时）

每当用户描述一个新的需求、修改请求或功能变更时：

1. 读取 `.teamwork/decisions/` 目录下的所有 JSON 文件
2. 对每个 `decision_key`，找到最新的 active 版本
   （被更新记录 supersedes 的自动排除）
3. 将用户请求与 active 决策做业务语义比对
4. 读取 `.teamwork/config.json` 中的 `team_members` 确定当前用户身份

### `human` 类型冲突 → 必须线下沟通

当用户请求与其他成员的人工明确决策冲突时：
- 立即告知：说明哪位成员在何时做了什么决策
- 引用动机：展示 `decision.motivation`
- 要求沟通：明确要求用户先与该成员线下确认
- 等待确认：用户必须回复"已沟通，可以继续"后才执行
- 不可跳过：即使你判断当前方案更优，也不能绕过

### `human_ai` 类型冲突 → 提醒，当前用户判断为准

- 告知用户存在冲突，简要展示原决策
- 说明这是人和 AI 共同做出的决策
- 当前用户可直接决定是否覆盖

### `ai` 类型冲突 → 简要提及，直接执行

- 一句话提及存在旧的 AI 决策
- 直接按当前用户要求执行

### 无冲突

正常执行，不做任何额外提示。
不要在没有冲突时主动告知"我检查了决策清单没有发现冲突"。

## 二、实时决策草稿维护

在整个对话过程中，维护决策草稿 `.teamwork/drafts/current.json`。

### 何时更新

1. 用户做出明确的业务决策（如"我们用方案A"）
2. 用户与你讨论后达成共识
3. 你自主做出了设计决策（用户未明确指定，你选择了方案）
4. 收到上下文折叠通知时，确认草稿完整性

### 何时不更新

- 纯代码 bug 修复、类型错误修正
- AI 理解偏差后的纠正
- 纯重构、格式化

### 草稿格式

与正式决策记录格式一致，标记为 draft：
```json
{
  "status": "draft",
  "session_id": "...",
  "entries": [
    {
      "decision_key": "feature-name-kebab-case",
      "status": "active",
      "requirement": { "what": "...", "why": "..." },
      "solution": { "approach": "...", "not_included": "..." },
      "decision": { "type": "human|human_ai|ai", "motivation": "...", "decided_by": "..." }
    }
  ]
}
```

### 更新方式

追加式更新：新 entry 追加到 entries 数组，不重写整个文件。

## 三、文件位置

- 决策记录：`.teamwork/decisions/*.json`
- 决策草稿：`.teamwork/drafts/current.json`
- 团队配置：`.teamwork/config.json`
