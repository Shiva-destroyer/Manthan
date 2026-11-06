const VENDORS: [prefix: string, vendor: string][] = [
  ["llama", "Meta"],
  ["qwen", "Alibaba"],
  ["phi", "Microsoft"],
  ["nomic", "Nomic"],
  ["deberta", "ProtectAI"],
  ["protectai", "ProtectAI"],
];

export function vendorOf(model: string): string | null {
  const name = model.toLowerCase();
  return VENDORS.find(([prefix]) => name.startsWith(prefix))?.[1] ?? null;
}
