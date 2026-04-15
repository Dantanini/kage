# Graph Report - .  (2026-04-14)

## Corpus Check
- Corpus is ~26,785 words - fits in a single context window. You may not need a graph.

## Summary
- 1098 nodes · 1648 edges · 93 communities detected
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 398 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]

## God Nodes (most connected - your core abstractions)
1. `PlanStore` - 121 edges
2. `PlanStatus` - 113 edges
3. `MemoryStore` - 69 edges
4. `SessionManager` - 61 edges
5. `Session` - 28 edges
6. `PlanExecutor` - 18 edges
7. `WorktreeManager` - 17 edges
8. `TestWorkflowSteps` - 17 edges
9. `TestPlanLifecycle` - 16 edges
10. `_check_auth()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `Tests for conductor memory layer — Phase 0 of kage v2.  The conductor needs br` --uses--> `MemoryStore`  [INFERRED]
  tests\test_conductor_memory.py → memory.py
- `Create a minimal dev-journal structure with INDEX.md and log.md.` --uses--> `MemoryStore`  [INFERRED]
  tests\test_conductor_memory.py → memory.py
- `Global context should include INDEX.md content.` --uses--> `MemoryStore`  [INFERRED]
  tests\test_conductor_memory.py → memory.py
- `Global context should include recent log entries.` --uses--> `MemoryStore`  [INFERRED]
  tests\test_conductor_memory.py → memory.py
- `Log should be truncated to max_log_lines.` --uses--> `MemoryStore`  [INFERRED]
  tests\test_conductor_memory.py → memory.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (68): Enum, _clear_file(), _parse_item_metadata(), PlanStore, PlanStore v2 — three-file plan management, no LLM needed.  Three separate file, Read all three files combined (for display)., Append to draft.md. No LLM involved., Write Opus output to planned.md, clear draft.md. (+60 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (89): _build_app(), build_document_prompt(), build_photo_prompt(), _build_plan_recovery(), _check_auth(), cmd_deep(), cmd_done(), cmd_evening() (+81 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (37): Session 管理 — 追蹤活躍對話，支援 --resume 和 lifecycle hooks。, Close session and run end hooks. Now async., Run all start hooks. Returns list of error messages (empty = all OK)., Run all end hooks. Returns list of error messages (empty = all OK)., Reset the auto-save timer. Fires end hooks after delay_minutes of inactivity., Session, _make_hook(), Tests for session module — hooks, lifecycle, and management. (+29 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (19): build_prompt(), _has_checklist(), PromptSpec, PromptSpec framework — program-controlled prompt assembly.  Each action (plan,, Assemble prompt from spec + program-provided inputs.     Raises KeyError if a r, Validate that output contains at least one checklist item., Tests for prompt_specs — PromptSpec framework + /plan specs., Verify /morning specs exist, models, and input contracts. (+11 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (26): MemoryWriter, path(), Persistent memory layer — inspired by Claude Code's memdir system.  Reads/writ, Read global knowledge base context from INDEX.md and log.md.          These fi, Build the memory prefix to inject into prompts. Empty string if no memory., Build a prompt that asks Claude to update the memory files.          Args:, Event-driven writer for immediate memory updates.      Writes directly to stru, Get a structured memory file path. Returns None if dir doesn't exist. (+18 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (24): PlanExecutor, Executor — worktree-based parallel task execution engine.  Each task runs in a, Execute a single task in a worktree., Execute a phase of tasks. Group by repo for parallelism control., Execute all phases sequentially. Within each phase, repos run in parallel., Manages git worktrees for isolated task execution., Create a worktree for the given branch name., Remove a worktree and its branch. (+16 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (20): Tests for workflows module., Test result formatting., Test step builders produce correct structure., Test workflow execution chain., TestFormatResults, TestRunWorkflow, TestWorkflowSteps, build_evening_steps() (+12 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (9): Tests for PlanStore v2 — three-file plan management., Each section is its own file, no cross-contamination., Three files coexist: draft.md / planned.md / completed.md., TestArchive, TestContextInjection, TestDelete, TestPause, TestPlanLifecycle (+1 more)

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (10): Tests for memory module., If kage-memory/ dir doesn't exist but kage-memory.md does, use the file., Test persistent memory read/write., If both dir and file exist, prefer the directory., Test abnormal exit detection via .needs_recovery marker., If unlink fails (e.g. permission denied), catch and return empty., Test structured memory directory support (active-tasks, lessons-learned, session, TestMemoryStore (+2 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (9): Tests for release script — commit parsing and PR content generation., Generate PR body with grouped changelog., Ensure get_commits_between uses remote refs after fetch., Parse git log --oneline output into structured commit data., Generate concise PR title from parsed commits., TestGenerateBody, TestGenerateTitle, TestGetCommitsBetween (+1 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (14): Tests for auto_deploy — decision logic for automated deployment., Detect when origin/main has commits not in local main., Check if bot has no active sessions (based on timestamp file)., No file = bot hasn't been used = idle., Corrupt file should be treated as idle (safe to deploy)., Build Telegram notification message for deploy result., Decide whether to retry deployment after being skipped due to active bot., Hour 0 (03:00) — first skip, should retry later. (+6 more)

### Community 11 - "Community 11"
Cohesion: 0.12
Nodes (26): build_notify_message(), clear_attempt(), deploy(), get_attempt(), has_new_commits(), is_bot_idle(), load_env(), log() (+18 more)

### Community 12 - "Community 12"
Cohesion: 0.09
Nodes (13): _load_task_done(), Tests for scripts/task_done.py — branch completion notification.  NOTE: Source, Telegram callback_data limit is 64 bytes., Test the send function calls Telegram API correctly., Load task_done module from cached source, bypassing filesystem., Import task_done module fresh each test., Test notification message formatting., Test inline keyboard structure. (+5 more)

### Community 13 - "Community 13"
Cohesion: 0.09
Nodes (12): Tests for plan state recovery after bot restart.  When bot restarts (crash, co, PLANNED plan → button to start execution., DRAFT plan → message mentions draft., Test that post_init calls _build_plan_recovery and sends message., Test _build_plan_recovery() output for each plan state., EMPTY plan → no recovery message., EXECUTING plan → message includes pending item count., EXECUTING plan → message includes the next task description. (+4 more)

### Community 14 - "Community 14"
Cohesion: 0.14
Nodes (20): _make_callback_query(), _make_message(), Tests for task_pr and task_ask callback handling in bot.py., Create a mock callback query update., When user replies to a task_ask prompt, Claude should answer with branch context, Create a mock text message update, optionally replying to another message., task_pr:<branch> should run scripts/pr.sh for that branch., task_ask:<branch> should prompt user to reply with question. (+12 more)

### Community 15 - "Community 15"
Cohesion: 0.14
Nodes (16): make_run_side_effect(), Tests for commit.py branch guard functionality., Create a side_effect function that simulates git commands., commit.py should refuse to commit on protected branches., Committing on main should exit with error., Committing on develop is allowed (small changes rule)., Committing on feat/* should work normally., Unit tests for branch guard in commit.py. (+8 more)

### Community 16 - "Community 16"
Cohesion: 0.14
Nodes (19): _make_callback_update(), _make_update_with_message(), Tests for release inline button — preview shows button, callback executes releas, Clicking confirm button should execute release.py and report result., Create a mock Update with message for command handlers., Clicking cancel button should dismiss without running release., Create a mock Update with callback_query for button clicks., cmd_release preview message should contain an inline confirm button. (+11 more)

### Community 17 - "Community 17"
Cohesion: 0.11
Nodes (9): Tests for scripts/pr.sh — enforce PR base is always develop., pr.sh must enforce --base develop and block PRs from protected branches., Script must hardcode --base develop., Should refuse to open PR when on main branch., Should refuse to open PR from develop (develop→develop makes no sense)., Should proceed (dry-run) on a feature branch., When stdin is not a TTY (non-interactive), --fill should be added., Script should check if stdin is a TTY and add --fill accordingly. (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.26
Nodes (16): _get_all_replies(), _make_subprocess_mock(), _make_update(), Tests: restart always proceeds even on git errors, but reports them first.  Co, Error details must be sent to user BEFORE restart., os._exit(0) must be called regardless of git errors., test_all_git_ops_fail_restart_still_proceeds(), test_checkout_error_reported() (+8 more)

### Community 19 - "Community 19"
Cohesion: 0.12
Nodes (8): Tests for router module., Parse router.py source to catch duplicate dict keys that Python silently overwri, Test that commands route to the correct model and intent., Test fallback behavior for non-command messages., Ensure COMMAND_ROUTES has no duplicate keys (Python dicts silently overwrite)., TestCommandRouting, TestDefaultRouting, TestNoDuplicateKeys

### Community 20 - "Community 20"
Cohesion: 0.12
Nodes (6): Tests for notify module — shared Telegram notification utilities., Build notification message for memory auto-save events., send_telegram_message sends via Telegram Bot API., No token = no request, no crash., TestBuildMemorySaveMessage, TestSendTelegramMessage

### Community 21 - "Community 21"
Cohesion: 0.15
Nodes (11): _make_update(), Tests for /status command — monitor running claude subprocesses., Test _get_claude_status() process detection., Test /status command handler., Test the kill button from /status., test_auth_required(), test_no_process_shows_idle(), test_running_process_shows_info_with_buttons() (+3 more)

### Community 22 - "Community 22"
Cohesion: 0.14
Nodes (7): Tests for branch guard — prevent commits on protected branches., pre-commit hook should block commits on main and develop., Simulate running the pre-commit hook as if on a given branch., The pre-commit hook must have a branch protection check., Standalone branch_guard.sh should be testable independently., TestBranchGuardInHook, TestBranchGuardScript

### Community 23 - "Community 23"
Cohesion: 0.19
Nodes (13): _make_journal(), Tests for conductor memory layer — Phase 0 of kage v2.  The conductor needs br, Create a minimal dev-journal structure with INDEX.md and log.md., Global context should include INDEX.md content., Global context should include recent log entries., Log should be truncated to max_log_lines., Should return empty string if INDEX.md and log.md don't exist., build_context_prefix should include both kage-memory and global context. (+5 more)

### Community 24 - "Community 24"
Cohesion: 0.19
Nodes (6): _make_update(), Tests for /plan delete N — bot command parsing and response., test_delete_no_number_shows_numbered_list(), test_delete_non_integer_shows_usage(), test_delete_out_of_range_shows_error(), test_delete_valid_calls_delete_item()

### Community 25 - "Community 25"
Cohesion: 0.2
Nodes (11): _make_update(), Tests for /restart git pull behavior., Restart should write notify file; post_init should send notification., Restart should pull both repos before exiting., test_restart_continues_even_if_pull_fails(), test_restart_notifies_pull_failure(), test_restart_pulls_both_repos(), test_restart_saves_memory_before_pull() (+3 more)

### Community 26 - "Community 26"
Cohesion: 0.14
Nodes (10): Tests for /status non-blocking behavior.  /status must respond immediately eve, Application must allow concurrent update processing., Application should be built with concurrent_updates=True., Verify /status is registered with block=False., The CommandHandler for /status must have block=False., Verify _build_app produces a concurrent-enabled app., _build_app should set concurrent_updates=True., TestBuildAppConcurrent (+2 more)

### Community 27 - "Community 27"
Cohesion: 0.24
Nodes (11): create_pr(), generate_body(), generate_title(), get_commits_between(), main(), parse_commits(), Generate PR body with changelog grouped by type., Get git log --oneline between two remote branches.      Uses origin/ prefix to (+3 more)

### Community 28 - "Community 28"
Cohesion: 0.18
Nodes (4): Tests for photo message handling — prompt builder and handler logic., Prompt should instruct Claude to use Read tool for the image., Test the extracted build_photo_prompt helper., TestBuildPhotoPrompt

### Community 29 - "Community 29"
Cohesion: 0.18
Nodes (3): Tests for plan execution queue — select items and order via buttons., In-memory queue for tracking user-selected execution order., TestPlanQueue

### Community 30 - "Community 30"
Cohesion: 0.29
Nodes (4): _check_git_ready(), Tests for restart/release git safety — ensure failures are caught and reported., Mirror of bot._check_git_ready for testing.      Args:         checkout_resul, TestCheckGitReady

### Community 31 - "Community 31"
Cohesion: 0.33
Nodes (7): _make_proc(), Tests for context injection behaviour in _run_claude_once.  Plan context (plan, test_inject_plan_false_skips_plan_context(), test_inject_plan_true_empty_plan_adds_nothing(), test_inject_plan_true_includes_plan_context(), test_resume_never_injects_plan(), TestRunClauceOnceInjectPlan

### Community 32 - "Community 32"
Cohesion: 0.33
Nodes (8): _mock_plan_store(), Tests for EXECUTING → PLANNED downgrade on restart.  When bot restarts and pla, post_init should downgrade EXECUTING → PLANNED when no subprocess., test_executing_with_process_stays_executing(), test_executing_without_process_becomes_planned(), test_planned_not_affected(), test_recovery_message_after_downgrade_is_planned(), TestDowngradeExecutingOnRestart

### Community 33 - "Community 33"
Cohesion: 0.36
Nodes (7): build_keyboard(), build_message(), main(), Format the notification message., Build inline keyboard with Open PR and Ask buttons., Send task completion notification with inline buttons., send_task_done()

### Community 34 - "Community 34"
Cohesion: 0.25
Nodes (3): Tests for plan error handling improvements., Markdown list without checkbox should fail., test_has_checklist_wrong_format()

### Community 35 - "Community 35"
Cohesion: 0.39
Nodes (7): Tests for plan execution repo dispatch — Phase 2 of kage v2.  When a plan task, Mirror of bot._resolve_task_repo for testing without heavy imports., _resolve_task_repo(), test_resolve_task_repo_empty(), test_resolve_task_repo_known(), test_resolve_task_repo_none(), test_resolve_task_repo_unknown()

### Community 36 - "Community 36"
Cohesion: 0.29
Nodes (3): Tests for document/PDF message handling., Test the extracted build_document_prompt helper., TestBuildDocumentPrompt

### Community 37 - "Community 37"
Cohesion: 0.33
Nodes (5): build_memory_save_message(), tg_notify.py — Shared Telegram notification utilities.  Used by bot.py (memory, Send a plain text message via Telegram Bot API.      Returns True on success,, Build notification message for memory auto-save events., send_telegram_message()

### Community 38 - "Community 38"
Cohesion: 0.5
Nodes (3): Model 路由 — 預設 Sonnet，指令切換，工作流腳本控制。, Route message. Commands switch model, otherwise use default or current session m, route()

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (2): main(), run()

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (2): main(), send()

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (2): Design: Thin Shell — Bot as Relay Not Brain, Kage — Telegram to Claude Code Relay Bot

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (2): Origin: LLM→CandidateIssue→Rule from Time-Loop Game, Task: Pattern Detector

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (2): Design: Scripts for Deterministic Tasks, Decision: No LLM in Pattern Detection

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Legacy property — returns single file path for backward compat.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Parse a checklist line into {task, branch, repo}.         Format: - [ ] task de

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (0): 

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Should exit 1 when on a protected branch.

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Should exit 0 when on a feature branch.

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): develop allows small direct commits per branch strategy rules.

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Notification failure should not crash the bot.

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Preview message should have reply_markup with confirm button.

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Confirm button callback_data should be 'release_confirm'.

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): When there are no commits, no inline button should be shown.

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): release_confirm callback should run release.py (no --dry-run).

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): After release, the original message should be edited with the result.

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): If release.py fails, error should be shown.

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): release_cancel should not execute release.py.

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Cancel should edit message to show cancellation.

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): git checkout failure must NOT block restart.

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): git pull failure must NOT block restart.

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): Even if ALL git operations fail, restart must proceed.

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): Checkout error details must appear in user message.

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): Pull error details must appear in user message.

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): All errors (checkout + pull) must be reported, not just the first.

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): When git succeeds, no error/warning message should appear.

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): Error message must be sent BEFORE os._exit (i.e., before restart).

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): Restart should git pull both kage and journal repos.

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): If git pull fails, user should see a warning.

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): Pull failure should NOT block restart.

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): Memory should be saved before pull (existing behavior preserved).

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): cmd_restart should write .restart_notify with chat_id before exit.

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): post_init should send restart notification and delete .restart_notify.

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): post_init should not send notification if .restart_notify doesn't exist.

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (1): No claude subprocess → return None.

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (1): Detected claude process → return dict with pid, model, elapsed.

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): Should correctly extract sonnet model name.

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): /status with no running process → idle message.

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): /status with running process → info + kill/wait buttons.

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): /status should check admin auth.

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): Clicking kill button should kill the claude process.

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): Should call scripts/pr.sh with the branch name.

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): Should show PR URL on success.

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): Should show error when pr.sh fails.

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): Should show branch name and ask user to reply.

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): Should tell user to reply to this message.

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): Reply to task_ask prompt should include branch in Claude prompt.

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (1): After answering, should show [開 PR] [追問] buttons again.

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): Regular messages (not replying to task_ask) should not trigger Q&A.

### Community 89 - "Community 89"
Cohesion: 1.0
Nodes (1): Replies to different branch prompts should each get correct branch context.

### Community 90 - "Community 90"
Cohesion: 1.0
Nodes (0): 

### Community 91 - "Community 91"
Cohesion: 1.0
Nodes (1): Design: LLM for Reasoning Only

### Community 92 - "Community 92"
Cohesion: 1.0
Nodes (1): Code-Defined Workflows

## Knowledge Gaps
- **237 isolated node(s):** `Load .env file into environment.`, `Run a git command and return stdout.`, `Check if origin/main has commits not in local main.`, `Check if bot has no active session based on last activity timestamp.`, `Build Telegram notification message.` (+232 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 41`** (2 nodes): `Design: Thin Shell — Bot as Relay Not Brain`, `Kage — Telegram to Claude Code Relay Bot`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (2 nodes): `Origin: LLM→CandidateIssue→Rule from Time-Loop Game`, `Task: Pattern Detector`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (2 nodes): `Design: Scripts for Deterministic Tasks`, `Decision: No LLM in Pattern Detection`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Legacy property — returns single file path for backward compat.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Parse a checklist line into {task, branch, repo}.         Format: - [ ] task de`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `deploy-develop.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Should exit 1 when on a protected branch.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Should exit 0 when on a feature branch.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `develop allows small direct commits per branch strategy rules.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Notification failure should not crash the bot.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `Preview message should have reply_markup with confirm button.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Confirm button callback_data should be 'release_confirm'.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `When there are no commits, no inline button should be shown.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `release_confirm callback should run release.py (no --dry-run).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `After release, the original message should be edited with the result.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `If release.py fails, error should be shown.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `release_cancel should not execute release.py.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Cancel should edit message to show cancellation.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `git checkout failure must NOT block restart.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `git pull failure must NOT block restart.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `Even if ALL git operations fail, restart must proceed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `Checkout error details must appear in user message.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `Pull error details must appear in user message.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `All errors (checkout + pull) must be reported, not just the first.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `When git succeeds, no error/warning message should appear.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `Error message must be sent BEFORE os._exit (i.e., before restart).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `Restart should git pull both kage and journal repos.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `If git pull fails, user should see a warning.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `Pull failure should NOT block restart.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `Memory should be saved before pull (existing behavior preserved).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `cmd_restart should write .restart_notify with chat_id before exit.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `post_init should send restart notification and delete .restart_notify.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `post_init should not send notification if .restart_notify doesn't exist.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `No claude subprocess → return None.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `Detected claude process → return dict with pid, model, elapsed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `Should correctly extract sonnet model name.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `/status with no running process → idle message.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `/status with running process → info + kill/wait buttons.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `/status should check admin auth.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `Clicking kill button should kill the claude process.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `Should call scripts/pr.sh with the branch name.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `Should show PR URL on success.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `Should show error when pr.sh fails.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `Should show branch name and ask user to reply.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `Should tell user to reply to this message.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `Reply to task_ask prompt should include branch in Claude prompt.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (1 nodes): `After answering, should show [開 PR] [追問] buttons again.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `Regular messages (not replying to task_ask) should not trigger Q&A.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (1 nodes): `Replies to different branch prompts should each get correct branch context.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 90`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 91`** (1 nodes): `Design: LLM for Reasoning Only`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 92`** (1 nodes): `Code-Defined Workflows`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.