"""Tests for plan state recovery after bot restart.

When bot restarts (crash, context full, manual restart, git pull),
post_init should detect plan state and notify the user with
actionable buttons + full context.
"""

from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock
import pytest


@pytest.fixture
def mock_plan_store():
    store = MagicMock()
    store.status = MagicMock()
    store.pending_items.return_value = []
    store.read_planned.return_value = ""
    store.read_completed.return_value = ""
    store.read_draft.return_value = ""
    store.parse_planned_items.return_value = []
    return store


class TestBuildRecoveryMessage:
    """Test _build_plan_recovery_message() output for each plan state."""

    def test_empty_returns_none(self, mock_plan_store):
        """EMPTY plan → no recovery message."""
        from plan_v2 import PlanStatus
        mock_plan_store.status = PlanStatus.EMPTY
        mock_plan_store.has_plan.return_value = False

        with patch("bot.plan_store", mock_plan_store):
            from bot import _build_plan_recovery
            result = _build_plan_recovery()
            assert result is None

    def test_executing_shows_pending_count(self, mock_plan_store):
        """EXECUTING plan → message includes pending item count."""
        from plan_v2 import PlanStatus
        mock_plan_store.status = PlanStatus.EXECUTING
        mock_plan_store.pending_items.return_value = [
            "- [ ] task A",
            "- [ ] task B",
            "- [ ] task C",
        ]
        mock_plan_store.read_completed.return_value = "- [x] task done"

        with patch("bot.plan_store", mock_plan_store):
            from bot import _build_plan_recovery
            result = _build_plan_recovery()
            assert result is not None
            msg, keyboard = result
            assert "3" in msg  # 3 pending items

    def test_executing_shows_next_task(self, mock_plan_store):
        """EXECUTING plan → message includes the next task description."""
        from plan_v2 import PlanStatus
        mock_plan_store.status = PlanStatus.EXECUTING
        mock_plan_store.pending_items.return_value = ["- [ ] 實作 /status 指令"]
        mock_plan_store.parse_planned_items.return_value = [
            {"task": "實作 /status 指令", "branch": "feat/status", "repo": "kage"}
        ]
        mock_plan_store.read_completed.return_value = ""

        with patch("bot.plan_store", mock_plan_store):
            from bot import _build_plan_recovery
            result = _build_plan_recovery()
            msg, keyboard = result
            assert "/status" in msg

    def test_executing_has_continue_and_pause_buttons(self, mock_plan_store):
        """EXECUTING plan → buttons: continue + pause."""
        from plan_v2 import PlanStatus
        mock_plan_store.status = PlanStatus.EXECUTING
        mock_plan_store.pending_items.return_value = ["- [ ] task A"]
        mock_plan_store.parse_planned_items.return_value = [
            {"task": "task A", "branch": None, "repo": None}
        ]
        mock_plan_store.read_completed.return_value = ""

        with patch("bot.plan_store", mock_plan_store):
            from bot import _build_plan_recovery
            msg, keyboard = _build_plan_recovery()
            button_data = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
            assert "plan_execute" in button_data
            assert "plan_pause" in button_data

    def test_executing_shows_completed_progress(self, mock_plan_store):
        """EXECUTING plan → message shows how many already completed."""
        from plan_v2 import PlanStatus
        mock_plan_store.status = PlanStatus.EXECUTING
        mock_plan_store.pending_items.return_value = ["- [ ] task C"]
        mock_plan_store.parse_planned_items.return_value = [
            {"task": "task C", "branch": None, "repo": None}
        ]
        mock_plan_store.read_completed.return_value = "- [x] task A\n- [x] task B"

        with patch("bot.plan_store", mock_plan_store):
            from bot import _build_plan_recovery
            msg, keyboard = _build_plan_recovery()
            assert "2" in msg  # 2 completed

    def test_planned_has_execute_button(self, mock_plan_store):
        """PLANNED plan → button to start execution."""
        from plan_v2 import PlanStatus
        mock_plan_store.status = PlanStatus.PLANNED
        mock_plan_store.pending_items.return_value = ["- [ ] task A", "- [ ] task B"]
        mock_plan_store.read_completed.return_value = ""

        with patch("bot.plan_store", mock_plan_store):
            from bot import _build_plan_recovery
            msg, keyboard = _build_plan_recovery()
            button_data = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
            assert "plan_execute" in button_data

    def test_draft_shows_draft_notice(self, mock_plan_store):
        """DRAFT plan → message mentions draft."""
        from plan_v2 import PlanStatus
        mock_plan_store.status = PlanStatus.DRAFT
        mock_plan_store.draft_items.return_value = ["- idea 1", "- idea 2"]

        with patch("bot.plan_store", mock_plan_store):
            from bot import _build_plan_recovery
            result = _build_plan_recovery()
            msg, keyboard = result
            assert "草稿" in msg


class TestPostInitRecovery:
    """Test that post_init calls _build_plan_recovery and sends message."""

    @pytest.mark.asyncio
    async def test_post_init_sends_recovery_on_executing(self):
        """post_init with EXECUTING plan → sends recovery to admin."""
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        mock_keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("▶️ 繼續", callback_data="plan_execute"),
        ]])

        with patch("bot._build_plan_recovery", return_value=("恢復訊息", mock_keyboard)), \
             patch("bot.ADMIN_ID", 123), \
             patch("bot.REPO_DIR", MagicMock()):
            from bot import post_init

            app = MagicMock()
            app.bot = AsyncMock()
            app.bot.set_my_commands = AsyncMock()

            # Mock notify file not existing
            with patch("pathlib.Path.exists", return_value=False):
                await post_init(app)

            # Should have sent recovery message to admin
            app.bot.send_message.assert_called()
            call_args = app.bot.send_message.call_args
            assert call_args[0][0] == 123
            assert "恢復訊息" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_post_init_no_message_on_empty(self):
        """post_init with EMPTY plan → no recovery message."""
        with patch("bot._build_plan_recovery", return_value=None), \
             patch("bot.ADMIN_ID", 123), \
             patch("bot.REPO_DIR", MagicMock()):
            from bot import post_init

            app = MagicMock()
            app.bot = AsyncMock()
            app.bot.set_my_commands = AsyncMock()
            app.bot.send_message = AsyncMock()

            with patch("pathlib.Path.exists", return_value=False):
                await post_init(app)

            # send_message should NOT have been called for plan recovery
            # (it might be called for restart notify, but not for plan)
            for call in app.bot.send_message.call_args_list:
                if len(call[0]) > 1:
                    assert "計畫" not in call[0][1]
