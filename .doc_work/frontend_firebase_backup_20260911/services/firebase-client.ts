"use client";

import { getApp, getApps, initializeApp } from "firebase/app";
import { getAuth, inMemoryPersistence, setPersistence, type Auth } from "firebase/auth";

interface PublicFirebaseConfiguration {
  apiKey: string;
  authDomain: string;
  projectId: string;
  storageBucket: string;
  messagingSenderId: string;
  appId: string;
  measurementId?: string;
}

let authentication: Promise<Auth> | null = null;

function isFirebaseConfiguration(value: unknown): value is PublicFirebaseConfiguration {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  return ["apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId"]
    .every((key) => typeof Reflect.get(value, key) === "string");
}

export function getFirebaseAuthentication(): Promise<Auth> {
  if (authentication) return authentication;
  authentication = (async () => {
    const response = await fetch("/api/auth/config", { cache: "no-store" });
    const configuration: unknown = await response.json();
    if (!response.ok || !isFirebaseConfiguration(configuration)) {
      throw new Error("Firebase Authentication is not configured");
    }
    const app = getApps().length ? getApp() : initializeApp(configuration);
    const auth = getAuth(app);
    await setPersistence(auth, inMemoryPersistence);
    return auth;
  })();
  return authentication;
}
