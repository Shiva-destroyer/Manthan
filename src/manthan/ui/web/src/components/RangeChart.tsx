import { pct } from "../lib/format.ts";

export type RangePoint = { label: string; value: number; lo: number | null; hi: number | null };

const W = 640;
const H = 280;
const L = 56; // room for the y labels
const R = 16;
const T = 16;
const B = 48; // room for the x labels
const y = (v: number) => T + (1 - v) * (H - T - B);

function range(p: RangePoint): string {
  return p.lo !== null && p.hi !== null ? `, likely between ${pct(p.lo)} and ${pct(p.hi)}` : "";
}

// One series of dots with a whisker for the stated range. A missing end means no whisker.
export function RangeChart({
  points,
  yLabel,
  title,
  target,
}: {
  points: RangePoint[];
  yLabel: string;
  title: string;
  target?: { value: number; label: string };
}) {
  const step = (W - L - R) / Math.max(points.length, 1);
  const x = (i: number) => L + step * (i + 0.5);
  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title} width="100%" style={{ maxWidth: W }}>
        <title>{title}</title>
        {[0, 0.25, 0.5, 0.75, 1].map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--color-line)" strokeWidth={1} />
            <text x={L - 8} y={y(v) + 4} textAnchor="end" fontSize={13} fill="var(--color-muted)">
              {pct(v)}
            </text>
          </g>
        ))}
        <line x1={L} x2={L} y1={T} y2={H - B} stroke="var(--color-wire)" strokeWidth={1} />
        <line x1={L} x2={W - R} y1={H - B} y2={H - B} stroke="var(--color-wire)" strokeWidth={1} />
        <text transform={`translate(14 ${(T + H - B) / 2}) rotate(-90)`} textAnchor="middle" fontSize={13} fill="var(--color-muted)">
          {yLabel}
        </text>
        {target && (
          <g>
            <line x1={L} x2={W - R} y1={y(target.value)} y2={y(target.value)} stroke="var(--color-ink)" strokeWidth={1} strokeDasharray="6 4" />
            <text x={W - R} y={y(target.value) - 6} textAnchor="end" fontSize={13} fill="var(--color-ink)">
              {target.label}
            </text>
          </g>
        )}
        {points.map((p, i) => (
          <g key={p.label}>
            {p.lo !== null && p.hi !== null && (
              <g stroke="var(--color-ink)" strokeWidth={2}>
                <line x1={x(i)} x2={x(i)} y1={y(p.lo)} y2={y(p.hi)} />
                <line x1={x(i) - 5} x2={x(i) + 5} y1={y(p.lo)} y2={y(p.lo)} />
                <line x1={x(i) - 5} x2={x(i) + 5} y1={y(p.hi)} y2={y(p.hi)} />
              </g>
            )}
            <circle cx={x(i)} cy={y(p.value)} r={5} fill="var(--color-teal)" stroke="var(--color-wire)" strokeWidth={1} />
            <circle cx={x(i)} cy={y(p.value)} r={14} fill="transparent">
              <title>{`${p.label}: ${pct(p.value)}${range(p)}`}</title>
            </circle>
            <text x={x(i)} y={H - B + 20} textAnchor="middle" fontSize={13} fill="var(--color-ink)">
              {p.label}
            </text>
          </g>
        ))}
      </svg>
      <div className="sr-only">
        <table>
          <caption>{title}</caption>
          <thead>
            <tr>
              <th scope="col">Item</th>
              <th scope="col">{yLabel}</th>
              <th scope="col">Likely range</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.label}>
                <th scope="row">{p.label}</th>
                <td>{pct(p.value)}</td>
                <td>{p.lo !== null && p.hi !== null ? `${pct(p.lo)} to ${pct(p.hi)}` : "not stated"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
