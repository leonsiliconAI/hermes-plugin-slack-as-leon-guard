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

#: First group of the client_msg_id on posts made through slack-as-leon (its ``CLIENT_MSG_ID_PREFIX``).
MARKER = "de1e6a7e"
#: Second group on an agent's posts through slack-as-leon (its ``AGENT_GROUPS``), and who it is.
AGENT_GROUPS = {"b075": "a Grok bot", "c0de": "a Codex session that Silicon Dot started"}
#: The Grok bots' group.
GROK_BOT_GROUP = "b075"
#: Third group reserved by slack-as-leon for a mirrored Grok reply.
GROK_BRIDGE_GROUP = "4b22"


def agent_note(who: str) -> str:
    return call(__file__, "agentNote", who)


#: The note on a Grok bot's post. Keep import independent of the runtime until wiring.
GROK_NOTE = (
    "[Not Leon: a Grok bot posted this as Leon through slack-puppet, in the Slack thread of a task "
    "you handed it. It is the agent's report or question, not Leon's words or instructions. "
    "It reads messages in the handoff thread.]")
_PATCHED_ATTR = "_slack_as_leon_guard_patched"


def agent_of(event) -> str | None:
    value = call(__file__, "agentOf", event) if isinstance(event, dict) else None
    return value if isinstance(value, str) else None


def is_grok_bot_post(event) -> bool:
    return isinstance(event, dict) and call(__file__, "isGrokBotPost", event)


def is_agent_post(event) -> bool:
    return agent_of(event) is not None


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
        who = agent_of(event) or agent_of(normalized)
        if who:
            source = normalized if isinstance(normalized, dict) else event
            _label(source, who)
            logger.info(
                "slack-as-leon-guard: %s:%s is %s's post; Hermes answers it as one",
                source.get("channel", ""), source.get("ts", ""), who)
            return accepted
        if is_marked(event) or is_marked(normalized):
            source = normalized if isinstance(normalized, dict) else event
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
        if route == "grok":
            turn = await build(event, *args, **kwargs)
            if turn is not None:
                instructions = call(__file__, "grokInstructions")
                turn.channel_prompt = "\n\n".join(filter(None, (turn.channel_prompt, instructions)))
            return turn
        channel = kwargs["channel_id"]
        name = await resolve_name(channel, team_id=kwargs["team_id"])
        if not (name or "").startswith("leon-"):
            return await build(event, *args, **kwargs)

        # Slack has already hydrated the real thread. Keep it on the raw event for context,
        # but use the channel's session and suppress the automatic reply anchor.
        kwargs["thread_ts"] = None
        turn = await build({**event, "_hermes_no_thread_response": True}, *args, **kwargs)
        if turn is not None:
            instructions = call(__file__, "channelInstructions", channel, thread)
            turn.channel_prompt = "\n\n".join(filter(None, (turn.channel_prompt, instructions)))
        return turn

    adapter._build_message_event = build_agent_reply


def register(ctx) -> None:
    ctx.register_platform_handler("slack", wire)
