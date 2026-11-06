// Field names copy the API exactly (src/manthan/ui/app.py and data.py).

export type Source = { id: string; path: string; label: string; live: boolean };

export type Campaign = {
  id: string;
  domain: string;
  config_hash: string;
  seed: number;
  created_at: string;
  label: string | null;
  status: string | null;
};

export type Rate = {
  name: string;
  domain: string;
  label: string;
  target: string | null;
  value: number;
  ci_low: number | null;
  ci_high: number | null;
  method: string | null;
  k: number | null;
  n: number | null;
};

export type RagPoint = { n_poison: number; value: number; ci_low: number | null; ci_high: number | null };
export type Defence = { layer: string; dasr: number; benign_acc: number | null; oracle: boolean };
export type OtherMetric = {
  name: string;
  value: number;
  ci_low: number | null;
  ci_high: number | null;
  method: string | null;
  domain: string;
};
export type HeatCell = { owasp_id: string; atlas_id: string; count: number };

export type Results = {
  rates: Rate[];
  rag_curve: RagPoint[];
  defences: Defence[];
  stacked: { value: number; method: string | null } | null;
  other: OtherMetric[];
  heatmap: HeatCell[];
};

export type JudgeResult = {
  name: string;
  fpr: number;
  tpr: number;
  accuracy: number;
  n: number;
  fpr_target: number;
  fpr_ok: boolean;
  fpr_ci: [number, number] | null;
  tpr_ci: [number, number] | null;
};

export type Calibration = {
  id: string;
  name: string;
  error: string | null;
  mtime?: string;
  tag?: string | null;
  split?: string | null;
  source?: string | null;
  n_items?: number | null;
  gold_counts?: Record<string, number> | null;
  fleiss_kappa?: number | null;
  pairwise_kappa?: Record<string, number>;
  judges?: JudgeResult[];
};

export type Check = { name: string; ok: boolean; detail: string };
export type ModelRow = {
  role: string;
  model: string;
  pulled: boolean | null;
  loaded: boolean | null;
  size_bytes?: number | null;
};
export type SystemInfo = { checks: Check[]; models: ModelRow[]; configs: { name: string; text: string; runnable?: boolean }[] };
export type Turn = { id: string; run_id: string; idx: number; role: string; content: string; latency_s: number | null };

export type RoleSettings = {
  model: string | null;
  keep_alive: string | null;
  temperature: number | null;
  temperature_why: string | null;
  num_predict: number | null;
};
export type Settings = {
  config: string | null;
  backend: string | null;
  seed: number;
  config_hash: string | null;
  roles: Record<string, RoleSettings>;
  guard: { kind: string; model: string; threshold: number; use_onnx: boolean } | null;
  use_defended_target: boolean | null;
  agent_lab: string | null;
  rag_k: number | null;
};

export type RunRow = { id: string; campaign_id: string; objective_id: string; target_label: string; status: string; domain: string };
export type CampaignDetail = { campaign: Campaign; runs: RunRow[] };
export type Resources = {
  free_ram_gb: number | null;
  ollama_ps: { name?: string }[] | null;
  ollama_error: string | null;
  budget_min: number | null;
  used_min: number | null;
};
