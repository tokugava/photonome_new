import { useState } from "react";
import { Button, Field } from "../components/Field";
import { input } from "../components/styles";
import { submitGenerateJob } from "../jobs";

export function GeneratePage({ userId }: { userId: string }) {
  const [prompt, setPrompt] = useState("TOK as an astronaut, cinematic lighting");
  const [steps, setSteps] = useState(28);
  const [size, setSize] = useState(1024);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function submit() {
    if (!prompt.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await submitGenerateJob({
        prompt: prompt.trim(),
        steps,
        width: size,
        height: size,
      });
      setMsg(`Submitted job ${res.data.jobId}`);
    } catch (e) {
      setMsg(`Failed: ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Field label="Prompt" hint={`Worker will load loras/${userId}.safetensors by default.`}>
        <textarea
          className={input("min-h-24")}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Steps">
          <input
            type="number"
            className={input()}
            value={steps}
            min={10}
            max={80}
            onChange={(e) => setSteps(Number(e.target.value))}
          />
        </Field>
        <Field label="Size (square)">
          <select className={input()} value={size} onChange={(e) => setSize(Number(e.target.value))}>
            {[512, 768, 1024, 1280].map((s) => (
              <option key={s} value={s}>
                {s}px
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Button onClick={submit} disabled={busy || !prompt.trim()}>
        {busy ? "Submitting..." : "Run generation"}
      </Button>
      {msg && <p className="text-sm text-slate-700">{msg}</p>}
    </div>
  );
}
