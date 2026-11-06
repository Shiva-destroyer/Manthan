export function Missing({ why }: { why: string }) {
  return (
    <span title={why}>
      —<span className="sr-only"> ({why})</span>
    </span>
  );
}
