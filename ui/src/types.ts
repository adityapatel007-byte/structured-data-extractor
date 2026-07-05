/**
 * Types mirror the FastAPI response contract from src/api/routers/extract.py.
 * Kept minimal — Pydantic v2 on the server is the source of truth.
 */

export type DocType = "invoice" | "receipt" | "filing";

export interface FieldConfidence {
  field: string;
  score: number;
  reasoning?: string | null;
}

export interface ExtractionWarning {
  field: string | null;
  message: string;
  severity: "info" | "warning" | "error";
}

export interface ExtractionResult<T = Record<string, unknown>> {
  document_type: string;
  data: T;
  field_confidences: FieldConfidence[];
  overall_confidence: number;
  warnings: ExtractionWarning[];
  raw_text_snippet: string | null;
}

export interface ExtractionMetrics {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms: number;
  cost_usd: number;
  model: string;
}

export interface ExtractResponse {
  result: ExtractionResult;
  metrics: ExtractionMetrics;
}

export interface APIErrorEnvelope {
  error: {
    code: string;
    message: string;
    request_id?: string | null;
    details?: Record<string, unknown>;
  };
}
