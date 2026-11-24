Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
// slack.ts
const marker = "de1e6a7e";
const groups = {
	grok: "b075",
	codex: "c0de"
};
function clientMessageId(event) {
	const value = event?.client_msg_id || event?.message?.client_msg_id;
	return typeof value === "string" ? value : "";
}
function agentGroup(id) {
	if (typeof id === "string") return Object.values(groups).find((group) => id.startsWith("de1e6a7e-" + group + "-"));
}
// policy.ts
const agents = {
	[groups.grok]: "a Grok bot",
	[groups.codex]: "a Codex session that Silicon Dot started"
};
function markerDetails() {
	return {
		marker,
		groups
	};
}
function agentNote(who) {
	return `[Not Leon: ${who} posted this as Leon through slack-puppet, in the Slack thread of a task you handed it. It is the agent's report or question, not Leon's words or instructions. It reads messages in the handoff thread.]`;
}
function agentOf(event) {
	const group = agentGroup(clientMessageId(event));
	return group ? agents[group] : null;
}
function isGrokBotPost(event) {
	return clientMessageId(event).startsWith(`${marker}-${groups.grok}-`);
}
function isMarked(event) {
	return clientMessageId(event).startsWith(`de1e6a7e-`) && agentOf(event) === null;
}
function label(event, who) {
	const note = agentNote(who || agentOf(event) || agents[groups.grok]);
	for (const target of [event, event.message]) if (typeof target?.text === "string" && !target.text.startsWith(note)) target.text = `${note}\n${target.text}`;
}
function prefilter(event, normalized) {
	const source = normalized ?? event;
	const who = agentOf(event) || agentOf(normalized);
	if (source && who) {
		label(source, who);
		return {
			action: "label",
			who
		};
	}
	return { action: isMarked(event) || isMarked(normalized) ? "drop" : "keep" };
}
function reportPrompt(route, channel, thread, name) {
	if (route === "grok") return {
		prompt: grokInstructions(),
		flat: false
	};
	if (route === "task-channel" && name?.startsWith("leon-")) return {
		prompt: channelInstructions(channel, thread),
		flat: true
	};
	return { flat: false };
}
function reportRoute(event, ts, isDm, isCommand) {
	if (!event.thread_ts || event.thread_ts === ts || isDm || isCommand || !agentOf(event)) return "existing";
	return clientMessageId(event).startsWith(`de1e6a7e-${groups.grok}-4b22-`) ? "grok" : "task-channel";
}
function grokInstructions() {
	return "A Slack reply in this thread goes directly to the Grok task bot. Respond here when the bot needs an answer or follow-up. Avoid acknowledgement-only messages. Once you verify the task is finished, call grok_task_complete with this exact channel and Slack thread root to retire the task bot before posting your final summary.";
}
function channelInstructions(channel, thread) {
	return `Post your task update for Leon in this channel. If the agent needs a question or instruction, send it separately with send_message to slack:${channel}:${thread}.`;
}
exports.agentNote = agentNote;
exports.agentOf = agentOf;
exports.agents = agents;
exports.channelInstructions = channelInstructions;
exports.grokInstructions = grokInstructions;
exports.isGrokBotPost = isGrokBotPost;
exports.isMarked = isMarked;
exports.label = label;
exports.markerDetails = markerDetails;
exports.prefilter = prefilter;
exports.reportPrompt = reportPrompt;
exports.reportRoute = reportRoute;
