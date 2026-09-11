import "server-only";

export const authCookieNames = {
  access: "aisteth_access_token",
} as const;

function requiredEnvironment(name: string): string {
  const value = process.env[name]?.trim();
  if (!value || value.includes("CHANGE_ME") || value.includes("YOUR_")) {
    throw new Error(`${name} is not configured`);
  }
  return value;
}

export function firebaseClientConfiguration() {
  const measurementId = process.env["NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID"]?.trim();
  return {
    apiKey: requiredEnvironment("NEXT_PUBLIC_FIREBASE_API_KEY"),
    authDomain: requiredEnvironment("NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN"),
    projectId: requiredEnvironment("NEXT_PUBLIC_FIREBASE_PROJECT_ID"),
    storageBucket: requiredEnvironment("NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET"),
    messagingSenderId: requiredEnvironment("NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID"),
    appId: requiredEnvironment("NEXT_PUBLIC_FIREBASE_APP_ID"),
    ...(measurementId ? { measurementId } : {}),
  };
}

export function secureCookie(): boolean {
  return process.env.NODE_ENV === "production";
}
