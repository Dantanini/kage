"""Tests for /plan delete N — bot command parsing and response."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from plan_v2 import PlanStore, PlanStatus


@pytest.fixture
def plan_store(tmp_path):
    return PlanStore(local_dir=str(tmp_path / ".local"))


def _make_update(text: str) -> MagicMock:
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


class TestPlanDeleteCommand:
    """Unit tests for /plan delete N parsing and response (no TG network)."""

    @pytest.mark.asyncio
    async def test_delete_valid_index_removes_item(self, plan_store):
        plan_store.append("keep this")
        plan_store.append("delete this")
        deleted = plan_store.delete_item(2)
        assert "delete this" in deleted
        assert "delete this" not in plan_store.read_draft()
        assert "keep this" in plan_store.read_draft()

    @pytest.mark.asyncio
    async def test_delete_invalid_index_returns_none(self, plan_store):
        plan_store.append("only item")
        result = plan_store.delete_item(99)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_last_item_empties_plan(self, plan_store):
        plan_store.append("solo")
        plan_store.delete_item(1)
        assert plan_store.status == PlanStatus.EMPTY
        assert not plan_store.has_plan()

    @pytest.mark.asyncio
    async def test_delete_planned_item(self, plan_store):
        plan_store.append("raw idea")
        plan_store.set_planned("- [ ] step A\n- [ ] step B")
        # draft is cleared after set_planned; planned items are index 1 and 2
        items = plan_store.all_items_numbered()
        assert len(items) == 2
        deleted = plan_store.delete_item(1)
        assert "step A" in deleted
        remaining = plan_store.pending_items()
        assert len(remaining) == 1
        assert "step B" in remaining[0]

    @pytest.mark.asyncio
    async def test_all_items_numbered_returns_global_index(self, plan_store):
        plan_store.append("draft 1")
        plan_store.append("draft 2")
        items = plan_store.all_items_numbered()
        indices = [idx for (_, _, idx) in items]
        assert indices == [1, 2]

    @pytest.mark.asyncio
    async def test_all_items_numbered_across_sections(self, plan_store):
        plan_store.append("draft idea")
        plan_store.set_planned("- [ ] planned task")
        plan_store.set_executing()
        plan_store.complete_item("planned task")
        plan_store.pause()
        plan_store.append("new idea")
        items = plan_store.all_items_numbered()
        file_types = [ft for (ft, _, _) in items]
        assert "completed" in file_types
        assert "draft" in file_types


class TestPlanDeleteBotParsing:
    """Integration-style tests: simulate cmd_plan with delete body."""

    @pytest.mark.asyncio
    async def test_delete_valid_calls_delete_item(self, plan_store, monkeypatch):
        """When body is 'delete 1', plan_store.delete_item(1) is called."""
        plan_store.append("task to delete")

        import bot
        monkeypatch.setattr(bot, "plan_store", plan_store)

        update = _make_update("/plan delete 1")
        ctx = MagicMock()

        with patch("bot._check_auth", return_value=AsyncMock(return_value=True)()):
            # Patch _check_auth to return True directly
            async def mock_auth(u):
                return True
            monkeypatch.setattr(bot, "_check_auth", mock_auth)
            await bot.cmd_plan(update, ctx)

        assert not plan_store.has_plan()
        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        assert "已刪除" in reply_text

    @pytest.mark.asyncio
    async def test_delete_out_of_range_shows_error(self, plan_store, monkeypatch):
        """When index doesn't exist, reply with error message."""
        plan_store.append("only item")

        import bot
        monkeypatch.setattr(bot, "plan_store", plan_store)

        update = _make_update("/plan delete 99")
        ctx = MagicMock()

        async def mock_auth(u):
            return True
        monkeypatch.setattr(bot, "_check_auth", mock_auth)
        await bot.cmd_plan(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "找不到" in reply_text

    @pytest.mark.asyncio
    async def test_delete_non_integer_shows_usage(self, plan_store, monkeypatch):
        """When N is not an integer, reply with usage hint."""
        plan_store.append("some item")

        import bot
        monkeypatch.setattr(bot, "plan_store", plan_store)

        update = _make_update("/plan delete abc")
        ctx = MagicMock()

        async def mock_auth(u):
            return True
        monkeypatch.setattr(bot, "_check_auth", mock_auth)
        await bot.cmd_plan(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "/plan delete" in reply_text

    @pytest.mark.asyncio
    async def test_delete_no_number_shows_numbered_list(self, plan_store, monkeypatch):
        """'/plan delete' without N shows numbered item list."""
        plan_store.append("item one")
        plan_store.append("item two")

        import bot
        monkeypatch.setattr(bot, "plan_store", plan_store)

        update = _make_update("/plan delete")
        ctx = MagicMock()

        async def mock_auth(u):
            return True
        monkeypatch.setattr(bot, "_check_auth", mock_auth)
        await bot.cmd_plan(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "1." in reply_text or "#1" in reply_text
