import { useState } from "react";
import { Button, Field } from "../components/Field";
import { input } from "../components/styles";
import { submitTrainJob } from "../jobs";
import { newId, uploadFile } from "../storage";

export function TrainPage({ userId }: { userId: string }) {
  const [files, setFiles] = useState<File[]>([]);
  const [steps, setSteps] = useState(1000);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function submit() {
    if (files.length < 8 || files.length > 10) {
      setMsg(`Pick 8–10 selfies (you have ${files.length})`);
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const batchId = newId();
      const paths: string[] = [];
      for (let i = 0; i < files.length; i++) {
        const f = files[i];
        const path = await uploadFile(userId, `train/${batchId}/${String(i).padStart(3, "0")}-${f.name}`, f);
        paths.push(path);
      }
      const res = await submitTrainJob({ imagePaths: paths, steps });
      setMsg(`Submitted training job ${res.data.jobId}`);
      setFiles([]);
    } catch (e) {
      setMsg(`Failed: ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Field label="Selfies (8–10)" hint="All uploaded to Firebase Storage before submission.">
        <input
          type="file"
          accept="image/*"
          multiple
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          className="text-sm"
        />
        <span className="text-xs text-slate-500">{files.length} selected</span>
      </Field>
      <Field label="Training steps">
        <input
          type="number"
          className={input("w-32")}
          value={steps}
          min={100}
          max={4000}
          step={50}
          onChange={(e) => setSteps(Number(e.target.value))}
        />
      </Field>
      <Button onClick={submit} disabled={busy || files.length < 8}>
        {busy ? "Uploading..." : "Run training"}
      </Button>
      {msg && <p className="text-sm text-slate-700">{msg}</p>}
    </div>
  );
}
