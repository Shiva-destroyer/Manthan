import tokens from "../design/tokens.json";

// Writes tokens.json to the root element as CSS variables, so the stylesheet never holds a second copy.
export function applyTokens(): void {
  const style = document.documentElement.style;
  for (const [name, hex] of Object.entries(tokens.color)) style.setProperty(`--color-${name}`, hex);
  for (const px of tokens.space_px) style.setProperty(`--space-${px}`, `${px}px`);
  for (const px of tokens.radius_px) style.setProperty(`--radius-${px}`, `${px}px`);
  for (const px of tokens.type.size_px) style.setProperty(`--size-${px}`, `${px}px`);
  style.setProperty("--fast", `${tokens.motion.fast_ms}ms`);
  style.setProperty("--slow", `${tokens.motion.slow_ms}ms`);
  style.setProperty("--ease", tokens.motion.ease);
}
