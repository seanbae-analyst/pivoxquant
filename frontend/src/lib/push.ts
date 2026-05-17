import { API } from "./endpoints";
import { apiFetch } from "./api";

const VAPID_PUBLIC_KEY = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || "";

export function isPushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export async function subscribeToPush(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null;

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return null;

  const registration = await navigator.serviceWorker.ready;

  const existing = await registration.pushManager.getSubscription();
  if (existing) {
    // Ensure backend knows about this subscription
    await sendSubscriptionToBackend(existing);
    return existing;
  }

  if (!VAPID_PUBLIC_KEY) {
    // F3-04 (2026-05-17): previously returned null silently. The caller
    // (components/pwa/push-permission.tsx) caught the null-return as
    // "subscription not needed" — UI dismissed the prompt as if push
    // had been enabled, but 0 actual subscriptions were ever created.
    // Throw so callers can surface a real error toast.
    throw new Error(
      "Push notifications not configured (NEXT_PUBLIC_VAPID_PUBLIC_KEY missing).",
    );
  }

  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
      .buffer as ArrayBuffer,
  });

  // Send subscription to backend
  await sendSubscriptionToBackend(subscription);

  return subscription;
}

export async function unsubscribeFromPush(): Promise<boolean> {
  if (!isPushSupported()) return false;

  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();

  if (!subscription) return true;

  // Remove from backend
  try {
    await apiFetch(API.push.unsubscribe, {
      method: "POST",
      body: JSON.stringify({ endpoint: subscription.endpoint }),
    });
  } catch {
    // Continue with local unsubscribe even if backend call fails
  }

  const success = await subscription.unsubscribe();
  return success;
}

export async function getPushSubscription(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null;
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}

export async function getPushStatus(): Promise<{
  subscribed: boolean;
  count: number;
}> {
  try {
    const res = await fetch(API.push.status, { credentials: "include" });
    if (!res.ok) return { subscribed: false, count: 0 };
    return res.json();
  } catch {
    return { subscribed: false, count: 0 };
  }
}

async function sendSubscriptionToBackend(
  subscription: PushSubscription,
): Promise<void> {
  try {
    await apiFetch(API.push.subscribe, {
      method: "POST",
      body: JSON.stringify({ subscription: subscription.toJSON() }),
    });
  } catch (err) {
    console.error("Failed to send push subscription to backend:", err);
  }
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}
