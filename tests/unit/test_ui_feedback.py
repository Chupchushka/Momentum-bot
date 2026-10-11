"""Tests for lifecycle status message updates."""

from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText

from src.bot.ui.messages import (
    MSG_DURATION_EXCEEDED,
    MSG_SIZE_EXCEEDED,
    STATUS_MESSAGES,
    create_status_updater,
)


@pytest.mark.asyncio
async def test_status_updater_maps_each_lifecycle_stage():
    edit_text = AsyncMock()
    update = create_status_updater(edit_text)

    for stage in ("SEARCHING", "DOWNLOADING", "CONVERTING", "SENDING"):
        await update(stage)

    assert [call.kwargs["text"] for call in edit_text.await_args_list] == [
        STATUS_MESSAGES[stage]
        for stage in ("SEARCHING", "DOWNLOADING", "CONVERTING", "SENDING")
    ]
    assert all(call.kwargs["parse_mode"] == "HTML" for call in edit_text.await_args_list)


@pytest.mark.asyncio
async def test_status_updater_preserves_custom_status_text():
    edit_text = AsyncMock()
    update = create_status_updater(edit_text)

    await update("Custom status")

    edit_text.assert_awaited_once_with(text="Custom status", parse_mode="HTML")


@pytest.mark.asyncio
async def test_status_updater_ignores_unchanged_message_error():
    edit_text = AsyncMock(
        side_effect=TelegramBadRequest(
            method=EditMessageText(chat_id=123, message_id=456, text="same status"),
            message="message is not modified",
        )
    )
    update = create_status_updater(edit_text)

    await update("DOWNLOADING")

    edit_text.assert_awaited_once_with(
        text=STATUS_MESSAGES["DOWNLOADING"], parse_mode="HTML"
    )


@pytest.mark.asyncio
async def test_status_updater_propagates_other_telegram_errors():
    edit_text = AsyncMock(
        side_effect=TelegramBadRequest(
            method=EditMessageText(chat_id=123, message_id=456, text="status"),
            message="message to edit not found",
        )
    )
    update = create_status_updater(edit_text)

    with pytest.raises(TelegramBadRequest, match="message to edit not found"):
        await update("DOWNLOADING")


def test_boundary_errors_have_user_facing_guidance():
    assert "20 minutes" in MSG_DURATION_EXCEEDED
    assert "50 MB" in MSG_SIZE_EXCEEDED
