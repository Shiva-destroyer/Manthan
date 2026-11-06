export type Lab = "prompt" | "agent" | "rag";
export type DeviceId = string;
export type Device = {
  id: DeviceId;
  label: string;
  icon: string | null;
  role: string | null;
  glossary: string;
  x: number;
  y: number; // x, y on a 1000 x 600 viewBox
};

const d = (id: string, label: string, icon: string | null, role: string | null, glossary: string, x: number, y: number): Device =>
  ({ id, label, icon, role, glossary, x, y });

export const LABS: Record<Lab, { devices: Device[]; wires: [DeviceId, DeviceId][] }> = {
  prompt: {
    devices: [
      d("attacker", "Attacker", null, "attacker", "attacker", 100, 300),
      d("guard", "Guard", "guard", null, "guard", 330, 140),
      d("target", "Target", null, "target", "target", 440, 300),
      d("rubric-judge", "Rubric judge", "rubric-judge", "judge", "rubric-judge", 700, 190),
      d("rule-check", "Rule check", "rule-check", null, "rule-check", 700, 410),
      d("results", "Results", "results-store", null, "results-store", 900, 300),
    ],
    wires: [
      ["attacker", "target"], ["attacker", "guard"], ["guard", "target"],
      ["target", "rubric-judge"], ["target", "rule-check"],
      ["rubric-judge", "results"], ["rule-check", "results"],
    ],
  },
  agent: {
    devices: [
      d("ollama", "Ollama", "ollama-host", null, "ollama", 150, 120),
      d("agent", "Agent", null, "target", "agent", 150, 300),
      d("mcp", "MCP", null, null, "mcp", 400, 300),
      d("mcp-legit", "Honest tool server", "mcp-server", null, "mcp-legit", 600, 120),
      d("mcp-malicious", "Hostile tool server", "mcp-server-malicious", null, "mcp-malicious", 600, 300),
      d("sandbox", "Sandbox", "sandbox", null, "sandbox", 800, 300),
      d("mock-exfil", "Fake data sink", "data-sink", null, "mock-exfil", 800, 480),
      d("internet", "Internet: blocked", "internet-blocked", null, "internet-blocked", 800, 120),
    ],
    wires: [
      ["agent", "ollama"], ["agent", "mcp"], ["mcp", "mcp-legit"], ["mcp", "mcp-malicious"],
      ["mcp-legit", "sandbox"], ["mcp-malicious", "sandbox"], ["sandbox", "mock-exfil"], ["sandbox", "internet"],
    ],
  },
  rag: {
    devices: [
      d("question", "Question", "question", null, "question", 80, 300),
      d("embedder", "Embedder", "embedder", "embed", "embed", 250, 110),
      d("document-store", "Document store", "document-store", null, "document-store", 480, 110),
      d("retrieval_filter", "Retrieval filter", "guard", null, "retrieval_filter", 480, 230),
      d("prompt_guard", "Prompt guard", "guard", null, "prompt_guard", 280, 430),
      d("context_sep", "Context separation", "guard", null, "context_sep", 280, 530),
      d("target", "Target", null, "target", "target", 560, 340),
      d("output_validator", "Output validator", "guard", null, "output_validator", 740, 430),
      d("rubric-judge", "Rubric judge", "rubric-judge", "judge", "rubric-judge", 740, 230),
      d("results", "Results", "results-store", null, "results-store", 900, 340),
    ],
    wires: [
      ["question", "embedder"], ["embedder", "document-store"], ["document-store", "retrieval_filter"],
      ["document-store", "target"], ["retrieval_filter", "target"],
      ["question", "target"], ["question", "prompt_guard"], ["question", "context_sep"],
      ["prompt_guard", "target"], ["context_sep", "target"],
      ["target", "output_validator"], ["target", "results"], ["output_validator", "results"],
      ["target", "rubric-judge"], ["rubric-judge", "results"],
    ],
  },
};

export function deviceForRole(role: string, lab: Lab): DeviceId | null {
  return LABS[lab].devices.find((x) => x.role === role)?.id ?? null;
}
