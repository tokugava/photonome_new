import { useState } from "react";
import { Button, Field } from "../components/Field";
import { input } from "../components/styles";
import { submitEditJob } from "../jobs";
import { newId, uploadFile } from "../storage";

const STYLES: { value: string; label: string }[] = [
  { value: "flat-cartoon", label: "Flat Cartoon" },
  { value: "lego", label: "LEGO" },
  { value: "paper-cutting", label: "Paper Cutting" },
  { value: "irasutoya", label: "Irasutoya" },
  { value: "ghibli", label: "Ghibli" },
  { value: "american-cartoon", label: "American Cartoon" },
  { value: "clay-toy", label: "Clay Toy" },
];

export function EditPage({ userId }: { userId: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [style, setStyle] = useState(STYLES[0].value);
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function submit() {
    if (!file) {
      setMsg("Pick an image first");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const id = newId();
      const path = await uploadFile(userId, `edit/${id}/${file.name}`, file);
      const res = await submitEditJob({ inputImagePath: path, style, prompt });
      setMsg(`Submitted job ${res.data.jobId}`);
      setFile(null);
      setPrompt("");
    } catch (e) {
      setMsg(`Failed: ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Field label="Source image" hint="Uploaded to Firebase Storage, then sent to edit_worker.">
        <input
          type="file"
          accept="image/*"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm"
        />
      </Field>
      <Field label="Style">
        <select className={input()} value={style} onChange={(e) => setStyle(e.target.value)}>
          {STYLES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Prompt (optional)" hint="Free-form instruction for the edit.">
        <input
          type="text"
          className={input()}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. make her smile"
        />
      </Field>
      <Button onClick={submit} disabled={busy || !file}>
        {busy ? "Submitting..." : "Run edit"}
      </Button>
      {msg && <p className="text-sm text-slate-700">{msg}</p>}
    </div>
  );
}
