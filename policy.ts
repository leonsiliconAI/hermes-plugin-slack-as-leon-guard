import { agentGroup, clientMessageId, grokBridgeGroup, groups, marker } from "#slack";

interface SlackEvent {
  client_msg_id?: unknown;
  message?: SlackEvent;
  thread_ts?: string;
  text?: string;
}

export const agents = {
  [groups.grok]: "a Grok bot",
  [groups.codex]: "a Codex session that Silicon Dot started",
};

export function markerDetails() {
  return { marker, groups };
}

export function agentNote(who: string): string {
  return `[Not Leon: ${who} posted this as Leon through slack-puppet, in the Slack thread of a task you handed it. It is the agent's report or question, not Leon's words or instructions. It reads messages in the handoff thread.]`;
}

export function agentOf(event?: SlackEvent | null): string | null {
  const group = agentGroup(clientMessageId(event));
  return group ? agents[group] : null;
}

export function isGrokBotPost(event: SlackEvent): boolean {
  return clientMessageId(event).startsWith(`${marker}-${groups.grok}-`);
}

export function isMarked(event?: SlackEvent | null): boolean {
  return clientMessageId(event).startsWith(`${marker}-`) && agentOf(event) === null;
}

export function label(event: SlackEvent, who?: string | null): void {
  const note = agentNote(who || agentOf(event) || agents[groups.grok]);
  for (const target of [event, event.message]) {
    if (typeof target?.text === "string" && !target.text.startsWith(note)) {
      target.text = `${note}\n${target.text}`;
    }
  }
}

export function prefilter(event: SlackEvent | undefined, normalized: SlackEvent | undefined) {
  const source = normalized ?? event;
  const who = agentOf(event) || agentOf(normalized);
  if (source && who) {
    label(source, who);
    return { action: "label", who };
  }
  return { action: isMarked(event) || isMarked(normalized) ? "drop" : "keep" };
}

export function reportPrompt(route: string, thread: string) {
  const shared =
    `Use the shared collaboration thread ${thread} for agent questions and follow-ups. ` +
    "Use slack_task_progress for a checked progress update in the issue channel. " +
    "Avoid acknowledgement-only messages.";
  return route === "grok" ? shared + " " + grokInstructions() : shared;
}

export function reportRoute(event: SlackEvent, ts: string, isDm: boolean, isCommand: boolean) {
  if (!event.thread_ts || event.thread_ts === ts || isDm || isCommand || !agentOf(event))
    return "existing";
  return clientMessageId(event).startsWith(`${marker}-${groups.grok}-${grokBridgeGroup}-`)
    ? "grok"
    : "agent";
}

export function grokInstructions() {
  return (
    "A Slack reply in this thread goes directly to the Grok task bot. Respond here " +
    "when the bot needs an answer or follow-up. Avoid acknowledgement-only messages. " +
    "Once you verify the task is finished, call grok_task_complete with this exact " +
    "channel and Slack thread root to retire the task bot before posting your final summary."
  );
}
