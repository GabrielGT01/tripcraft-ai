import type {
  ResumePayload,
  TripResponse,
} from "./types";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000"
).replace(/\/$/, "");

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

async function readApiError(
  response: Response,
): Promise<string> {
  try {
    const body = await response.json();

    if (typeof body?.detail === "string") {
      return body.detail;
    }

    return JSON.stringify(body);
  } catch {
    return (
      `Request failed with status ` +
      `${response.status}`
    );
  }
}

async function post<T>(
  path: string,
  body: unknown,
): Promise<T> {
  const response = await fetch(
    apiUrl(path),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    },
  );

  if (!response.ok) {
    throw new Error(
      await readApiError(response),
    );
  }

  return response.json() as Promise<T>;
}

export function startTrip(
  threadId: string,
  question: string,
): Promise<TripResponse> {
  return post<TripResponse>(
    "/api/trip/start",
    {
      thread_id: threadId,
      question,
    },
  );
}

export function resumeTrip(
  threadId: string,
  payload: ResumePayload,
): Promise<TripResponse> {
  return post<TripResponse>(
    "/api/trip/resume",
    {
      thread_id: threadId,
      ...payload,
    },
  );
}
