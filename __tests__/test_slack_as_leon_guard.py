"""Run against a Hermes checkout (see README): uses the real v0.23 Slack adapter."""

from __future__ import annotations

import importlib.util
import sys
import pathlib
import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import PlatformConfig
from gateway.platforms.base import _reply_anchor_for_event, _thread_metadata_for_source
from plugins.platforms.slack.adapter import SlackAdapter

_root = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("slack_as_leon_guard", _root / "__init__.py")
plugin = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = plugin
_spec.loader.exec_module(plugin)

LEON = "U0LEON00001"
MARKED = "de1e6a7e-ccdc-45d1-94bb-f80359112347"
GROK_BOT = "de1e6a7e-b075-45d1-94bb-f80359112347"
CODEX = "de1e6a7e-c0de-45d1-94bb-f80359112347"
LEONS_OWN = "3f2b1c4d-1111-4222-8333-944455556666"


@pytest.fixture()
def adapter(monkeypatch):
    monkeypatch.setenv("SLACK_REQUIRE_MENTION", "false")
    a = SlackAdapter(PlatformConfig(enabled=True, token="***"))
    a._app = MagicMock()
    a._app.client = AsyncMock()
    a._app.client.users_info = AsyncMock(
        return_value={"user": {"is_bot": False, "profile": {"display_name": "Leon"}}})
    a._app.client.conversations_info = AsyncMock(
        return_value={"ok": True, "channel": {"name": "agents"}})
    a._app.client.conversations_replies = AsyncMock(return_value={"ok": True, "messages": []})
    a._app.client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "1700000000.000050"})
    a._bot_user_id = "U_HERMES"
    a._running = True
    a.handle_message = AsyncMock()
    return a


def _event(ts: str, client_msg_id: str, **extra) -> dict:
    return {"type": "message", "text": "add milk to my list", "user": LEON, "channel": "C_TODO",
            "channel_type": "channel", "ts": ts, "client_msg_id": client_msg_id, **extra}


def test_marker_matches_the_mini_service():
    """The TypeScript service's CLIENT_MSG_ID_PREFIX must equal MARKER."""
    marker_ts = (_root.parents[1] / "packages/ai/leonsilicon/services/slack-as-leon/marker.ts").read_text()
    match = re.search(r'CLIENT_MSG_ID_PREFIX = "([0-9a-f]{8})"', marker_ts)
    assert match and match.group(1) == plugin.MARKER
    groups = dict(re.findall(r'(grok|codex): "([0-9a-f]{4})"', marker_ts))
    assert set(groups.values()) == set(plugin.AGENT_GROUPS)
    assert groups["grok"] == plugin.GROK_BOT_GROUP


@pytest.mark.asyncio
async def test_stock_adapter_answers_a_post_made_as_leon(adapter):
    """Documents the loop this plugin prevents."""
    await adapter._handle_slack_message(_event("1700000000.000001", MARKED))
    adapter.handle_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_post_made_as_leon_is_ignored(adapter):
    plugin.wire(None, adapter)
    await adapter._handle_slack_message(_event("1700000000.000002", MARKED))
    await adapter._handle_slack_message(
        _event("1700000000.000003", MARKED, thread_ts="1700000000.000001"))
    adapter.handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_mention_of_hermes_in_a_post_made_as_leon_is_ignored(adapter):
    plugin.wire(None, adapter)
    event = _event("1700000000.000004", MARKED, text="<@U_HERMES> can you check this")
    await adapter._handle_slack_message(event)
    await adapter._handle_slack_message({**event, "type": "app_mention"})
    adapter.handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_edit_of_a_post_made_as_leon_is_ignored(adapter):
    plugin.wire(None, adapter)
    original = _event("1700000000.000005", MARKED, text="<@U_HERMES> fixed typo")
    await adapter._handle_slack_message({
        "type": "message", "subtype": "message_changed", "channel": "C_TODO",
        "channel_type": "channel", "ts": "1700000009.000001", "event_ts": "1700000009.000001",
        "message": {**original, "edited": {"user": LEON, "ts": "1700000009.000001"}}})
    adapter.handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_leons_own_messages_still_reach_hermes(adapter):
    plugin.wire(None, adapter)
    await adapter._handle_slack_message(_event("1700000000.000006", LEONS_OWN))
    await adapter._handle_slack_message(
        {k: v for k, v in _event("1700000000.000007", "").items() if k != "client_msg_id"})
    assert adapter.handle_message.await_count == 2


def test_wire_is_idempotent_and_fails_closed(adapter, caplog):
    plugin.wire(None, adapter)
    wrapped = adapter._prefilter_inbound
    plugin.wire(None, adapter)
    assert adapter._prefilter_inbound is wrapped

    bare = MagicMock(spec=[])
    with caplog.at_level("WARNING"):
        plugin.wire(None, bare)
    assert "internals changed" in caplog.text


def test_is_marked():
    assert plugin.is_marked({"client_msg_id": MARKED})
    assert plugin.is_marked({"subtype": "message_changed", "message": {"client_msg_id": MARKED}})
    assert not plugin.is_marked({"client_msg_id": LEONS_OWN})
    assert not plugin.is_marked({"client_msg_id": "de1e6a7e"})
    assert not plugin.is_marked({})
    assert not plugin.is_marked(None)


@pytest.mark.asyncio
async def test_grok_bot_post_is_answered_and_labelled_not_leon(adapter):
    plugin.wire(None, adapter)
    await adapter._handle_slack_message(_event(
        "1700000000.000020", GROK_BOT, thread_ts="1700000000.000001",
        text="🤖 *Task slack:C_TODO/1700000000.000001*: Done, the list has milk."))
    adapter.handle_message.assert_awaited_once()
    turn = adapter.handle_message.await_args.args[0]
    assert turn.text.startswith(plugin.GROK_NOTE)
    assert "Done, the list has milk." in turn.text
    assert turn.source.thread_id == "1700000000.000001"


@pytest.mark.parametrize("client_msg_id", [
    GROK_BOT, CODEX, LEONS_OWN, "de1e6a7e-b075-4b22-8f9c-4d72cb551abb",
])
@pytest.mark.asyncio
async def test_task_channel_routes_agent_reports_to_the_channel(adapter, monkeypatch, client_msg_id):
    plugin.wire(None, adapter)
    adapter._app.client.conversations_info.return_value = {
        "ok": True, "channel": {"name": "leon-379-membership-form"}}
    hydrate = AsyncMock(return_value=("Previous task report", [], []))
    monkeypatch.setattr(adapter, "_hydrate_thread_context", hydrate)
    root = "1700000000.000001"
    await adapter._handle_slack_message(_event(
        "1700000000.000030", client_msg_id, thread_ts=root,
        text="<@U_HERMES> The form is ready."))

    adapter.handle_message.assert_awaited_once()
    turn = adapter.handle_message.await_args.args[0]
    assert hydrate.await_args.kwargs["event_thread_ts"] == root
    assert turn.channel_context == "Previous task report"
    assert turn.raw_message["thread_ts"] == root
    mirrored = "-4b22-" in client_msg_id
    expected_thread = root if client_msg_id == LEONS_OWN or mirrored else None
    assert turn.source.thread_id == expected_thread
    if expected_thread is None:
        assert _reply_anchor_for_event(turn) is None
        assert f"slack:C_TODO:{root}" in turn.channel_prompt
    if mirrored:
        assert "grok_task_complete" in turn.channel_prompt
    await adapter.send(turn.source.chat_id, "Task update", reply_to=_reply_anchor_for_event(turn),
                       metadata=_thread_metadata_for_source(turn.source))
    assert adapter._app.client.chat_postMessage.await_args.kwargs.get("thread_ts") == expected_thread


def test_only_hermes_own_posts_count_as_marked():
    assert plugin.is_marked({"client_msg_id": MARKED})
    assert not plugin.is_marked({"client_msg_id": GROK_BOT})
    assert plugin.is_grok_bot_post({"client_msg_id": GROK_BOT})
    assert not plugin.is_grok_bot_post({"client_msg_id": LEONS_OWN})
    event = {"text": "hi"}
    plugin._label(event)
    plugin._label(event)
    assert event["text"] == f"{plugin.GROK_NOTE}\nhi"


@pytest.mark.asyncio
async def test_codex_post_is_answered_and_labelled_as_codex(adapter):
    plugin.wire(None, adapter)
    await adapter._handle_slack_message(_event(
        "1700000000.000040", CODEX, thread_ts="1700000000.000001",
        text="🤖 *Task slack:C_TODO/1700000000.000001*: PR is up."))
    adapter.handle_message.assert_awaited_once()
    text = adapter.handle_message.await_args.args[0].text
    assert text.startswith(plugin.agent_note("a Codex session that Silicon Dot started"))
