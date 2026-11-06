const STEPS = [
  { x: 150, name: "Attacker", does: "writes a prompt" },
  { x: 450, name: "Target", does: "answers it" },
  { x: 750, name: "Judge", does: "scores the answer" },
  { x: 1050, name: "Results", does: "stores the score" },
];
const TOP = 40;
const BOTTOM = 140;
const MID = 90;

// One packet travels the loop. Under reduced motion it stays at its start, beside the attacker.
export function LoopDrawing() {
  return (
    <svg
      className="loop"
      viewBox="0 0 1200 220"
      role="img"
      aria-label="The loop in one sentence: the attacker writes a prompt, the target answers it, the judge scores the answer, the score is stored, and the attacker tries again."
    >
      {STEPS.slice(0, -1).map((s, i) => (
        <line key={s.name} x1={s.x + 100} y1={MID} x2={STEPS[i + 1]!.x - 100} y2={MID} stroke="var(--color-wire)" strokeWidth={1} />
      ))}
      <polyline
        points={`${STEPS[3]!.x},${BOTTOM} ${STEPS[3]!.x},180 ${STEPS[0]!.x},180 ${STEPS[0]!.x},${BOTTOM}`}
        fill="none"
        stroke="var(--color-wire)"
        strokeWidth={1}
      />
      <circle className="loop-packet" cx={300} cy={MID} r={7} fill="var(--color-saffron)" stroke="var(--color-wire)" strokeWidth={1} />
      {STEPS.map((s) => (
        <g key={s.name}>
          <rect x={s.x - 100} y={TOP} width={200} height={BOTTOM - TOP} rx={8} fill="var(--color-paper)" stroke="var(--color-wire)" strokeWidth={1} />
          <text x={s.x} y={MID - 8} textAnchor="middle" className="lab-label">{s.name}</text>
          <text x={s.x} y={MID + 16} textAnchor="middle" className="lab-label">{s.does}</text>
        </g>
      ))}
    </svg>
  );
}
