import type { LabEvent } from "./events.ts";

const upTo = (events: LabEvent[], seq: number) => events.filter((e) => e.seq <= seq);

export function systemPromptOf(events: LabEvent[], role: string): string | null {
  const req = events.find((e) => e.kind === "model.request" && e.role === role && Array.isArray(e.messages));
  const first = (req?.messages as { role?: unknown; content?: unknown }[] | undefined)?.find((m) => m.role === "system");
  return typeof first?.content === "string" ? first.content : null;
}

export function residentAt(events: LabEvent[], seq: number): string[] | null {
  const last = upTo(events, seq).filter((e) => e.kind === "phase.start" && Array.isArray(e.resident)).pop();
  return last ? (last.resident as unknown[]).map(String) : null;
}

export function guardLine(events: LabEvent[], seq: number): string | null {
  const g = upTo(events, seq).filter((e) => e.kind === "guard.score").pop();
  if (!g || typeof g.score !== "number" || typeof g.threshold !== "number") return null;
  return `Score ${g.score} against a threshold of ${g.threshold}. Above the threshold means blocked.`;
}
