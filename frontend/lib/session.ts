const THREAD_STORAGE_KEY = "tripcraft_thread_id";

function generateThreadId(): string {
  if (
    typeof window !== "undefined" &&
    window.crypto &&
    typeof window.crypto.randomUUID === "function"
  ) {
    return window.crypto.randomUUID();
  }

  return (
    `${Date.now()}-` +
    Math.random().toString(36).slice(2) +
    Math.random().toString(36).slice(2)
  );
}

export function getOrCreateThreadId(): string {
  const current =
    window.localStorage.getItem(
      THREAD_STORAGE_KEY,
    );

  if (current) {
    return current;
  }

  const threadId = generateThreadId();

  window.localStorage.setItem(
    THREAD_STORAGE_KEY,
    threadId,
  );

  return threadId;
}

export function createFreshThreadId(): string {
  const threadId = generateThreadId();

  window.localStorage.setItem(
    THREAD_STORAGE_KEY,
    threadId,
  );

  return threadId;
}
