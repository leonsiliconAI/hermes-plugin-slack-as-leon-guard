# @-/com.leonsilicon.hermes.plugins.slack-as-leon-guard

Hermes plugin that stops Hermes from answering the Slack messages it posted as Leon through the [slack-as-leon](https://github.com/leonsilicon/leonsilicon.ai/blob/main/packages/ai/leonsilicon/services/slack-as-leon/README.md) MCP server.

## Why

Hermes posts as Leon with Leon's own Slack web session, so Grok Bot bots (which answer only Leon) act on the message. Those posts look exactly like Leon's: same user, no `bot_id` or `app_id`. Captain Claude listens to Leon in every channel (`require_mention: false`), so stock Hermes wakes on its own post and answers it as if Leon had written it. `ignore_other_user_mentions` only skips posts that mention someone else, so plain posts and thread replies would loop.

## What it does

The server stamps every post with a `client_msg_id` whose first group is `de1e6a7e`; Leon's own Slack clients use random UUIDs. Slack keeps the id and delivers it in the event. The plugin wraps the live adapter's `_prefilter_inbound`, which every inbound `message` and `app_mention` event passes through, and drops events carrying the marker, edits included. It logs `slack-as-leon-guard: not answering <channel>:<ts>, Hermes posted it as Leon`.

The messages stay in Slack, and Hermes's thread context still shows them (as Leon's). If the adapter internals change, it logs a warning instead of patching.

## Delegated agents' posts

Replies mirrored by `slack22grokbot` carry the third UUID group `4b22`. Hermes answers them in the original Slack thread so its replies go back to Grok. The turn prompt tells Hermes how to retire a finished task bot with `grok_task_complete`.

Grok bots and Codex sessions post reports and questions through the same server. Their markers use `b075` and `c0de`, respectively. Hermes receives those events with a note identifying the author of the report.

In `#leon-` task channels, Hermes reads the handoff thread for context and posts its automatic reply in the main channel conversation. If the delegated agent needs a question or instruction, Hermes can send it separately to the handoff thread. In other channels Hermes answers the report in its thread. When Leon writes directly in a thread, Hermes answers him there.

## Install

```sh
hermes plugins install leonsiliconAI/hermes-plugin-slack-as-leon-guard --enable
```

See [migration steps](https://github.com/leonsilicon/leonsilicon.ai/blob/main/DEVELOPMENT.md#hermes-plugin-mirrors) for an existing install. Restart the gateway. The gateway log then shows `slack-as-leon-guard: Hermes ignores the Slack messages it posts as Leon`.

## Test

The tests drive the real Slack adapter, so they need a Hermes checkout (Captain Claude runs v0.23.0):

```sh
git -C ~/.hermes/hermes-agent worktree add --detach /tmp/hermes-v0.23.0 v0.23.0
cd /tmp/hermes-v0.23.0 && UV_PROJECT_ENVIRONMENT=/tmp/hermes-venv uv sync --frozen --extra slack
VIRTUAL_ENV=/tmp/hermes-venv uv pip install pytest pytest-asyncio
cd - && HERMES_HOME=$(mktemp -d) PYTHONPATH=/tmp/hermes-v0.23.0 /tmp/hermes-venv/bin/python -m pytest -q -p no:cacheprovider __tests__
```

One test pins the upstream behavior (stock Hermes answers a marked post), and one checks the marker against the service's `CLIENT_MSG_ID_PREFIX`.
