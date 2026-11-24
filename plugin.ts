import { fileURLToPath } from "node:url";

/** Hermes plugin name, as listed in `plugins.enabled`. */
export const pluginName = "slack-as-leon-guard";

/** Directory to copy (without `__tests__/`) to `$HERMES_HOME/plugins/slack-as-leon-guard/`. */
export const pluginDirectory = fileURLToPath(new URL(".", import.meta.url));

/** Files that make up the deployed plugin. */
export const pluginFiles = [
  "plugin.yaml",
  "__init__.py",
  "pyproject.toml",
  "_pythonmonkey.py",
  "policy.cjs",
] as const;

/** First group of the client_msg_id slack-as-leon stamps on its posts (`MARKER` in `__init__.py`). */
export const marker = "de1e6a7e";

/** Second group on a Grok bot's posts through slack-as-leon (`GROK_BOT_GROUP` in `__init__.py`). */
export const grokBotGroup = "b075";

/** Second group on a Codex session's posts through slack-as-leon (in `AGENT_GROUPS`, `__init__.py`). */
export const codexGroup = "c0de";
