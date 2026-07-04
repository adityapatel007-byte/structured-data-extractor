/**
 * Thin fetch client for the FastAPI backend.
 *
 * Dev: Vite proxies /api/* to http://localhost:8000. See vite.config.ts.
 * Prod: set VITE_API_BASE to your deployed API's origin.
 */
import type { APIErrorEnvelope, DocType, ExtractResponse } from "@/types";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";

export class APIError extends Error {
  code: string;
  requestId?: string | null;
  details?: Record<string, unknown>;

  constructor(envelope: APIErrorEnvelope["error"]) {
    super(envelope.message);
    this.code = envelope.code;
    this.requestId = envelope.request_id;
    this.details = envelope.details;
  }
}

async function parseError(res: Response): Promise<never> {
  let envelope: APIErrorEnvelope | null = null;
  try {
    envelope = (await res.json()) as APIErrorEnvelope;
  } catch {
    /* body wasn't JSON */
  }
  if (envelope?.error) throw new APIError(envelope.error);
  throw new APIError({ code: `http_${res.status}`, message: res.statusText });
}

export interface ExtractArgs {
  file: File;
  docType: DocType;
  model?: string;
}

export async function extract({ file, docType, model }: ExtractArgs): Promise<ExtractResponse> {
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("doc_type", docType);
  if (model) form.append("model", model);

  const res = await fetch(`${API_BASE}/extract`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) await parseError(res);
  return (await res.json()) as ExtractResponse;
}

export async function listSchemas(): Promise<{ doc_types: string[] }> {
  const res = await fetch(`${API_BASE}/schemas`);
  if (!res.ok) await parseError(res);
  return await res.json();
}

export async function health(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) await parseError(res);
  return await res.json();
}
