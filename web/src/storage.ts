import { ref, uploadBytes } from "firebase/storage";
import { storage } from "./firebase";

export async function uploadFile(userId: string, path: string, file: File): Promise<string> {
  const objectPath = `uploads/${userId}/${path}`;
  const blobRef = ref(storage, objectPath);
  await uploadBytes(blobRef, file, { contentType: file.type });
  return objectPath;
}

export function newId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}
