# Task: Pattern Detector — 自動偵測重複 pattern 並建議開 issue

> 狀態：待開發
> 優先級：feature
> Branch：`feat/pattern-detector` from `develop`
> 開發方式：TDD

## 背景

Dante 目前手動發現 kage 重複出現的 pattern 才請 Claude 補功能。如果系統能自動偵測重複 pattern 並建議開 issue，就能加速改善循環。

這個想法源自遊戲專案的「LLM → CandidateIssue → 人工 review → 固化成規則」機制（見 `dev-journal/projects/time-loop-game-design.md`），先在 kage 實作簡化版。

## 設計

### 新增 `pattern_detector.py`

純 Python 分析，不 call LLM。分析 session 的 qa_log 找出 pattern。

```python
@dataclass
class CandidateIssue:
    pattern_type: str    # "repeated_question" | "manual_workaround" | "error_retry" | "missing_feature"
    description: str     # 人類可讀的描述
    evidence: list[str]  # 觸發這個偵測的 qa_log 片段
    confidence: float    # 0.0-1.0

def detect_patterns(qa_log: list[tuple[str, str]]) -> list[CandidateIssue]:
    """分析 qa_log，回傳偵測到的 candidate issues。"""
```

### 偵測類型

1. **Repeated Question** — 同 session 內問了非常相似的問題 2+ 次
   - 用簡單的 token overlap / jaccard similarity，不需要 LLM
   - threshold: similarity > 0.6 且間隔 > 1 輪對話

2. **Manual Workaround** — 使用者反覆手動做同一件事
   - 偵測 qa_log 中出現多次相似的「指令型」訊息
   - 例如反覆說 "幫我 git pull"、"幫我重啟"

3. **Error Retry** — 同一件事失敗後重試
   - 偵測 response 中包含 error/失敗 + 下一輪類似 prompt

4. **Missing Feature Hint** — 使用者說了「每次都要...」「又要...」「能不能自動...」
   - 關鍵字偵測：每次、又要、能不能、自動、太麻煩

### 整合點：end-hook

```python
# bot.py — 註冊新 hook
def _make_pattern_detect_hook():
    async def hook(session):
        if len(session.qa_log) < 3:
            return
        issues = detect_patterns(session.qa_log)
        if not issues:
            return
        msg = format_candidate_issues(issues)
        send_telegram_message(msg, token=token, chat_id=admin_id)
    return hook

sessions.register_end_hook(_make_pattern_detect_hook)
```

### 輸出格式（Telegram 通知）

```
🔍 偵測到 2 個 candidate issues：

1. [repeated_question] 本次對話中重複問了類似問題 3 次
   證據：「怎麼重啟」「幫我重啟」「restart 怎麼用」

2. [missing_feature] 使用者提到「每次都要手動...」
   證據：「每次都要手動 git pull 好麻煩」
```

## TDD 計畫

### Test Cases（先寫）

```python
# tests/test_pattern_detector.py

# --- detect_patterns 基本行為 ---
def test_empty_log_returns_no_issues():
    """qa_log 為空時不產生 issue"""

def test_short_log_returns_no_issues():
    """qa_log < 3 輪時不產生 issue"""

# --- Repeated Question ---
def test_detects_repeated_similar_questions():
    """相似問題出現 2+ 次應偵測為 repeated_question"""

def test_ignores_different_questions():
    """不同問題不應觸發 repeated_question"""

# --- Manual Workaround ---
def test_detects_repeated_manual_commands():
    """多次出現類似指令型訊息應偵測為 manual_workaround"""

# --- Error Retry ---
def test_detects_error_then_retry():
    """response 含錯誤 + 下一輪類似 prompt 應偵測為 error_retry"""

def test_ignores_error_without_retry():
    """只有錯誤但沒重試不應觸發"""

# --- Missing Feature Hint ---
def test_detects_missing_feature_keywords():
    """包含「每次」「能不能自動」等關鍵字應偵測"""

def test_ignores_normal_conversation():
    """一般對話不應觸發 missing_feature"""

# --- CandidateIssue 資料結構 ---
def test_candidate_issue_has_required_fields():
    """CandidateIssue 應包含 pattern_type, description, evidence, confidence"""

# --- format_candidate_issues ---
def test_format_empty_issues():
    """空 list 回傳空字串"""

def test_format_multiple_issues():
    """多個 issue 應格式化為可讀的 Telegram 訊息"""
```

### 實作順序

1. 定義 `CandidateIssue` dataclass
2. 實作 `_similarity(a, b)` — 簡單 jaccard similarity
3. 實作 `_detect_repeated_questions(qa_log)` + tests pass
4. 實作 `_detect_manual_workaround(qa_log)` + tests pass
5. 實作 `_detect_error_retry(qa_log)` + tests pass
6. 實作 `_detect_missing_feature(qa_log)` + tests pass
7. 實作 `detect_patterns()` 整合 + tests pass
8. 實作 `format_candidate_issues()` + tests pass
9. 寫 end-hook 整合到 bot.py
10. 跑全部 tests，確認不影響現有 109 tests

## 關鍵設計決策

- **不 call LLM**：pattern detection 用純 Python，確定性、零成本、可測試
- **只產生 candidate**：不自動開 GitHub issue，發 Telegram 通知讓 Dante 決定
- **end-hook 觸發**：不在每條訊息後分析，只在 session 結束時一次性分析
- **低誤報優先**：寧可漏偵測也不要頻繁推送垃圾通知。confidence threshold 設高一點

## 現有架構參考

- Hook 系統：`session.py` — `SessionHook = Callable[[Session], Awaitable[None]]`
- Hook 註冊：`bot.py:115-116` — `sessions.register_end_hook(factory)`
- 通知：`tg_notify.py` — `send_telegram_message(msg, token, chat_id)`
- 現有 tests：`tests/` — 109 tests，pytest + asyncio
