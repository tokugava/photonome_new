export type JobKind = "edit" | "train" | "generate";
export type JobStatus = "queued" | "running" | "success" | "error";

export type JobDoc = {
  jobId: string;
  userId: string;
  kind: JobKind;
  status: JobStatus;
  params: Record<string, unknown>;
  outputPath?: string;
  outputUrl?: string;
  error?: string;
  createdAt?: { seconds: number; nanoseconds: number } | null;
  updatedAt?: { seconds: number; nanoseconds: number } | null;
};

export type EditParams = {
  inputImagePath: string;
  style: string;
  prompt?: string;
};

export type TrainParams = {
  imagePaths: string[];
  steps?: number;
};

export type GenerateParams = {
  prompt: string;
  loraPath?: string;
  steps?: number;
  width?: number;
  height?: number;
};
