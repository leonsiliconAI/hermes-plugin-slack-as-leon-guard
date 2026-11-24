"""Keep Hermes from answering the Slack messages it posted as Leon.

Hermes posts as Leon through the ``slack-as-leon`` MCP server (a Cloudflare Worker), which uses Leon's own
Slack web session so the Grok bots (and any other bot that answers only Leon) act on the message.
Those posts are indistinguishable from Leon's: same user, no ``bot_id``/``app_id``. Hermes listens to
Leon everywhere (``require_mention: false``), so without this plugin it would wake on its own post
and answer it as if Leon had written it, possibly in a loop.

The server stamps every such post with a ``client_msg_id`` whose first group is ``MARKER``. Slack keeps
it and delivers it in the message event (Leon's Slack clients use random UUIDs). This plugin wraps
the live adapter's ``_prefilter_inbound``, which every inbound ``message`` / ``app_mention`` event
passes through, and drops events that carry the marker, edits included. Nothing else changes: the
messages stay in Slack, and thread context still shows them.

One kind of marked post is let through: an agent's, posted through the same server to talk to
Hermes in the Slack thread of a task Hermes handed it, a Grok bot's (second group ``b075``) or a
Codex session's that Silicon Dot started (``c0de``). Those posts are Leon's too as far as Slack can
tell, so the plugin starts their text with a note saying who wrote it (``agent_note``), and Hermes
answers them as the agent's report. In ``#leon-`` task channels manually posted reports use the
channel's session. Messages mirrored by slack22grokbot keep their Slack thread as the reply target.

It fails closed: if the adapter internals it relies on disappear, it logs a warning, so check the
gateway log after a Hermes update.
"""

from __future__ import annotations

import functools
import logging

from ._pythonmonkey import call


logger = logging.getLogger(__name__)

_PATCHED_ATTR = "_slack_as_leon_guard_patched"


def agent_note(who: str) -> str:
    return call(__file__, "agentNote", who)


def is_grok_bot_post(event) -> bool:
    return isinstance(event, dict) and call(__file__, "isGrokBotPost", event)


def is_marked(event) -> bool:
    return isinstance(event, dict) and call(__file__, "isMarked", event)


def _label(event, who: str | None = None) -> None:
    if isinstance(event, dict):
        call(__file__, "label", event, who)


def wire(native, adapter) -> None:
    """``register_platform_handler`` factory: patch this adapter instance once."""
    if getattr(adapter, _PATCHED_ATTR, False):
        return
    prefilter = getattr(adapter, "_prefilter_inbound", None)
    if not callable(prefilter):
        logger.warning(
            "slack-as-leon-guard: Slack adapter internals changed (no _prefilter_inbound); "
            "Hermes may answer its own messages posted as Leon")
        return

    @functools.wraps(prefilter)
    async def guarded(event, *args, **kwargs):
        accepted = await prefilter(event, *args, **kwargs)
        if accepted is None:
            return None
        normalized = accepted[0] if isinstance(accepted, tuple) and accepted else None
        decision = call(__file__, "prefilter", event if isinstance(event, dict) else None,
                        normalized if isinstance(normalized, dict) else None)
        source = normalized if isinstance(normalized, dict) else (event or {})
        if decision["action"] == "label":
            logger.info(
                "slack-as-leon-guard: %s:%s is %s's post; Hermes answers it as one",
                source.get("channel", ""), source.get("ts", ""), decision["who"])
        elif decision["action"] == "drop":
            logger.info(
                "slack-as-leon-guard: not answering %s:%s, Hermes posted it as Leon",
                source.get("channel", ""), source.get("ts", ""))
            return None
        return accepted

    adapter._prefilter_inbound = guarded
    setattr(adapter, _PATCHED_ATTR, True)
    logger.info(
        "slack-as-leon-guard: Hermes ignores the Slack messages it posts as Leon, "
        "and answers agents' posts (Grok bots, Codex sessions) labelled as theirs")

    build = getattr(adapter, "_build_message_event", None)
    resolve_name = getattr(adapter, "_resolve_channel_name", None)
    if not (callable(build) and callable(resolve_name)):
        logger.warning(
            "slack-as-leon-guard: Slack adapter internals changed; agent reports keep their thread")
        return

    @functools.wraps(build)
    async def build_agent_reply(event, *args, **kwargs):
        thread = event.get("thread_ts")
        route = call(
            __file__, "reportRoute", event, kwargs.get("ts"),
            kwargs.get("is_dm", False), kwargs.get("is_command_text", False),
        )
        if route == "existing":
            return await build(event, *args, **kwargs)
        channel = kwargs.get("channel_id", "")
        name = await resolve_name(channel, team_id=kwargs["team_id"]) if route == "task-channel" else None
        plan = call(__file__, "reportPrompt", route, channel, thread, name)
        if plan["flat"]:
            # Slack has hydrated the real thread; keep it on the event for context.
            kwargs["thread_ts"] = None
            event = {**event, "_hermes_no_thread_response": True}
        turn = await build(event, *args, **kwargs)
        if turn is not None and plan.get("prompt"):
            turn.channel_prompt = "\n\n".join(filter(None, (turn.channel_prompt, plan["prompt"])))
        return turn

    adapter._build_message_event = build_agent_reply


def register(ctx) -> None:
    ctx.register_platform_handler("slack", wire)
