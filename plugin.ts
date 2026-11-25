import { fileURLToPath } from "node:url";
import { groups, marker as postMarker } from "#slack";

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

/** First group of the client_msg_id slack-as-leon stamps on its posts. */
export const marker = postMarker;

/** Second group on a Grok bot's posts through slack-as-leon. */
export const grokBotGroup = groups.grok;

/** Second group on a Codex session's posts through slack-as-leon. */
export const codexGroup = groups.codex;
