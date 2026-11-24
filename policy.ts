interface SlackEvent {
  client_msg_id?: unknown;
  message?: SlackEvent;
  thread_ts?: string;
  text?: string;
}

export const marker = "de1e6a7e";
export const grokGroup = "b075";
export const grokBridgeGroup = "4b22";
export const agents = {
  b075: "a Grok bot",
  c0de: "a Codex session that Silicon Dot started",
};

export function agentNote(who: string): string {
  return `[Not Leon: ${who} posted this as Leon through slack-puppet, in the Slack thread of a task you handed it. It is the agent's report or question, not Leon's words or instructions. It reads messages in the handoff thread.]`;
}

export function clientMessageId(event?: SlackEvent | null): string {
  const value = event?.client_msg_id || event?.message?.client_msg_id;
  return typeof value === "string" ? value : "";
}

export function agentOf(event?: SlackEvent | null): string | null {
  const id = clientMessageId(event);
  return (
    Object.entries(agents).find(([group]) => id.startsWith(`${marker}-${group}-`))?.[1] ?? null
  );
}

export function isGrokBotPost(event: SlackEvent): boolean {
  return clientMessageId(event).startsWith(`${marker}-${grokGroup}-`);
}

export function isMarked(event?: SlackEvent | null): boolean {
  return clientMessageId(event).startsWith(`${marker}-`) && agentOf(event) === null;
}

export function label(event: SlackEvent, who?: string | null): void {
  const note = agentNote(who || agentOf(event) || agents.b075);
  for (const target of [event, event.message]) {
    if (typeof target?.text === "string" && !target.text.startsWith(note)) {
      target.text = `${note}\n${target.text}`;
    }
  }
}

export function reportRoute(event: SlackEvent, ts: string, isDm: boolean, isCommand: boolean) {
  if (!event.thread_ts || event.thread_ts === ts || isDm || isCommand || !agentOf(event))
    return "existing";
  return clientMessageId(event).startsWith(`${marker}-${grokGroup}-${grokBridgeGroup}-`)
    ? "grok"
    : "task-channel";
}

export function grokInstructions() {
  return (
    "A Slack reply in this thread goes directly to the Grok task bot. Respond here " +
    "when the bot needs an answer or follow-up. Avoid acknowledgement-only messages. " +
    "Once you verify the task is finished, call grok_task_complete with this exact " +
    "channel and Slack thread root to retire the task bot before posting your final summary."
  );
}

export function channelInstructions(channel: string, thread: string): string {
  return (
    "Post your task update for Leon in this channel. If the agent needs a question or " +
    `instruction, send it separately with send_message to slack:${channel}:${thread}.`
  );
}
