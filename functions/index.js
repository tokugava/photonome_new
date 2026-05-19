const { setGlobalOptions } = require("firebase-functions/v2");
const { onCall, HttpsError } = require("firebase-functions/v2/https");
const { onMessagePublished } = require("firebase-functions/v2/pubsub");
const logger = require("firebase-functions/logger");
const admin = require("firebase-admin");
const { PubSub } = require("@google-cloud/pubsub");

admin.initializeApp();
const db = admin.firestore();
const storage = admin.storage();
const pubsub = new PubSub();

setGlobalOptions({ maxInstances: 10, region: "europe-west3" });

const TOPICS = {
  edit: "edit-jobs",
  train: "train-jobs",
  generate: "generate-jobs",
};
const COMPLETION_TOPIC = "job-completions";

function newJobId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

async function createJob(kind, userId, params) {
  const jobId = newJobId();
  const doc = {
    userId,
    kind,
    status: "queued",
    params,
    createdAt: admin.firestore.FieldValue.serverTimestamp(),
    updatedAt: admin.firestore.FieldValue.serverTimestamp(),
  };
  await db.collection("jobs").doc(jobId).set(doc);
  const message = { userId, jobId, ...params };
  const data = Buffer.from(JSON.stringify(message));
  await pubsub.topic(TOPICS[kind]).publishMessage({ data });
  return jobId;
}

function requireAuth(request) {
  if (!request.auth) {
    throw new HttpsError("unauthenticated", "Sign-in required");
  }
  return request.auth.uid;
}

exports.submitEditJob = onCall(async (request) => {
  const uid = requireAuth(request);
  const { inputImagePath, style, prompt } = request.data ?? {};
  if (!inputImagePath || !style) {
    throw new HttpsError("invalid-argument", "inputImagePath and style are required");
  }
  const jobId = await createJob("edit", uid, { inputImagePath, style, prompt: prompt ?? "" });
  logger.info("edit_submitted", { jobId, uid });
  return { jobId };
});

exports.submitTrainJob = onCall(async (request) => {
  const uid = requireAuth(request);
  const { imagePaths, steps } = request.data ?? {};
  if (!Array.isArray(imagePaths) || imagePaths.length < 8 || imagePaths.length > 10) {
    throw new HttpsError("invalid-argument", "imagePaths must contain 8-10 entries");
  }
  const jobId = await createJob("train", uid, { imagePaths, steps: steps ?? 1000 });
  logger.info("train_submitted", { jobId, uid, n: imagePaths.length });
  return { jobId };
});

exports.submitGenerateJob = onCall(async (request) => {
  const uid = requireAuth(request);
  const { prompt, loraPath, steps, width, height } = request.data ?? {};
  if (!prompt) {
    throw new HttpsError("invalid-argument", "prompt is required");
  }
  const params = {
    prompt,
    loraPath: loraPath ?? `loras/${uid}.safetensors`,
    steps: steps ?? 28,
    width: width ?? 1024,
    height: height ?? 1024,
  };
  const jobId = await createJob("generate", uid, params);
  logger.info("generate_submitted", { jobId, uid });
  return { jobId };
});

exports.onJobCompletion = onMessagePublished(COMPLETION_TOPIC, async (event) => {
  const payload = event.data.message.json;
  if (!payload || !payload.jobId) {
    logger.warn("completion_missing_jobId", { payload });
    return;
  }
  const update = {
    status: payload.status,
    updatedAt: admin.firestore.FieldValue.serverTimestamp(),
  };
  if (payload.outputPath) {
    update.outputPath = payload.outputPath;
    try {
      const objectPath = payload.outputPath.replace(/^gs:\/\/[^/]+\//, "");
      const [url] = await storage
          .bucket()
          .file(objectPath)
          .getSignedUrl({ action: "read", expires: Date.now() + 7 * 24 * 60 * 60 * 1000 });
      update.outputUrl = url;
    } catch (err) {
      logger.warn("signed_url_failed", { jobId: payload.jobId, error: String(err) });
    }
  }
  if (payload.error) update.error = payload.error;
  await db.collection("jobs").doc(payload.jobId).set(update, { merge: true });
  logger.info("completion_recorded", { jobId: payload.jobId, status: payload.status });
});
