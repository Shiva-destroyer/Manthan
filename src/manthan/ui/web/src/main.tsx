import { createRoot } from "react-dom/client";
import { App } from "./App.tsx";
import { applyTokens } from "./lib/tokens.ts";
import "./styles.css";

applyTokens();
createRoot(document.getElementById("root")!).render(<App />);
