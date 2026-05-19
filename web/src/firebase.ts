import { initializeApp } from "firebase/app";
import { getAnalytics, isSupported as analyticsSupported } from "firebase/analytics";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";
import { getStorage } from "firebase/storage";
import { getFunctions } from "firebase/functions";

const firebaseConfig = {
  apiKey: "AIzaSyCxP5KH4PrcLTs-VHF-vaIHMHLI0dxFs2I",
  authDomain: "photonome.firebaseapp.com",
  projectId: "photonome",
  storageBucket: "photonome.appspot.com",
  messagingSenderId: "576917048224",
  appId: "1:576917048224:web:e5bc9fc4bea66168fc72c5",
  measurementId: "G-MY3GPWDPT6",
};

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
export const storage = getStorage(app);
export const functions = getFunctions(app, "europe-west3");

void analyticsSupported().then((ok) => {
  if (ok) getAnalytics(app);
});
