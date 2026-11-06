import { useState } from "react";
import { ActionButton } from "../components/ActionButton.tsx";
import { Empty } from "../components/Empty.tsx";
import { Info } from "../components/Info.tsx";
import { Missing } from "../components/Missing.tsx";
import { useApi } from "../lib/api.ts";
import { bytesToGB } from "../lib/format.ts";
import { lookup } from "../lib/glossary.ts";
import type { SystemInfo } from "../lib/types.ts";
import { vendorOf } from "../lib/vendor.ts";

const OLLAMA_DOWN = "Ollama is not reachable.";
const yesNo = (v: boolean | null) => (v === null ? <Missing why={OLLAMA_DOWN} /> : v ? "yes" : "no");

function Configs({ configs }: { configs: SystemInfo["configs"] }) {
  const [name, setName] = useState("");
  const chosen = configs.find((c) => c.name === name) ?? configs[0];
  if (!chosen) return <p>No config files were found next to the running config.</p>;
  return (
    <>
      <div className="picker">
        <label>
          <span className="muted">Config file</span>
          <select value={chosen.name} onChange={(e) => setName(e.target.value)}>
            {configs.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <pre className="config" tabIndex={0} aria-label={`Contents of ${chosen.name}`}>
        {chosen.text}
      </pre>
      <p className="muted">Config files are read-only here. Edit them in a text editor.</p>
    </>
  );
}

export function SystemPage() {
  const { data, error } = useApi<SystemInfo>("/api/system");
  if (error) return (
    <>
      <h1>System</h1>
      <Empty what={error.message} how="Check that `manthan ui` is running, then reload." />
    </>
  );
  if (!data) return (
    <>
      <h1>System</h1>
      <p className="muted">Loading…</p>
    </>
  );
  const failing = data.checks.filter((c) => !c.ok).length;
  return (
    <>
      <h1>System</h1>
      <section aria-labelledby="h-ready">
        <h2 id="h-ready">Ready to run</h2>
        <p>
          {failing === 0
            ? "All checks pass."
            : `${failing} of ${data.checks.length} ${failing === 1 ? "check fails" : "checks fail"}.`}
        </p>
        {data.checks.map((c) => (
          <p key={c.name} className="row">
            <strong>{lookup(c.name)?.term ?? c.name}</strong> {c.ok ? "passes" : "fails"}
            <Info name={c.name} /> <span className="mono muted">{c.detail}</span>
          </p>
        ))}
        <ActionButton name="init" body={{}} label="Create folders" />
      </section>
      <section aria-labelledby="h-models">
        <h2 id="h-models">Models</h2>
        <p>
          {data.models.length} models are set up.{" "}
          {data.models.some((m) => m.pulled === null)
            ? "Ollama is not reachable, so pulled and loaded status is unknown."
            : `${data.models.filter((m) => m.pulled).length} are pulled.`}
        </p>
        <div className="scroll-x">
          <table>
            <thead>
              <tr>
                <th scope="col">Model</th>
                <th scope="col">Role</th>
                <th scope="col">Size</th>
                <th scope="col">Pulled</th>
                <th scope="col">Loaded now</th>
              </tr>
            </thead>
            <tbody>
              {data.models.map((m) => (
                <tr key={m.role}>
                  <th scope="row">
                    <span className="badge">
                      <span className="muted">{vendorOf(m.model)}</span>
                      <span className="mono">{m.model}</span>
                    </span>
                  </th>
                  <td>
                    {lookup(m.role)?.term ?? m.role}
                    <Info name={m.role} />
                  </td>
                  <td>{m.size_bytes == null ? <Missing why={m.pulled === false ? "This model is not pulled." : OLLAMA_DOWN} /> : bytesToGB(m.size_bytes)}</td>
                  <td>{yesNo(m.pulled)}</td>
                  <td>{yesNo(m.loaded)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data.models.some((m) => m.pulled === false) && (
          <>
            <ActionButton name="models_pull" body={{}} label="Show the download commands" />
            <p className="muted">Manthan never downloads models. Run the commands it shows in a terminal.</p>
          </>
        )}
      </section>
      <section aria-labelledby="h-config">
        <h2 id="h-config">Config</h2>
        <Configs configs={data.configs} />
      </section>
    </>
  );
}
