/**
 * Sample documents surfaced as one-click "Try it" buttons on the landing page.
 * Each sample points at a file in /public/samples/ that ships with the frontend.
 */

import type { DocType } from "@/types";

export interface SampleDoc {
  id: string;
  label: string;
  docType: DocType;
  path: string;
  description: string;
}

export const SAMPLE_DOCS: SampleDoc[] = [
  {
    id: "coffee-receipt",
    label: "Coffee receipt",
    docType: "receipt",
    path: "/samples/coffee_receipt.png",
    description: "A short cafe receipt — merchant, total, tax.",
  },
  {
    id: "software-invoice",
    label: "Software invoice",
    docType: "invoice",
    path: "/samples/software_invoice.pdf",
    description: "A B2B software invoice with line items and net-30 terms.",
  },
];

export async function loadSampleAsFile(sample: SampleDoc): Promise<File> {
  const res = await fetch(sample.path);
  if (!res.ok) {
    throw new Error(`Sample not found: ${sample.path} (HTTP ${res.status})`);
  }
  const blob = await res.blob();
  const type = blob.type || guessMimeFromPath(sample.path);
  // Static hosts can return index.html for missing assets — guard against
  // shipping that to the API as if it were a real document.
  if (type.startsWith("text/html")) {
    throw new Error(
      `Sample "${sample.label}" is not installed on this deployment yet — try uploading your own file.`
    );
  }
  const filename = sample.path.split("/").pop() ?? "sample";
  return new File([blob], filename, { type });
}

function guessMimeFromPath(path: string): string {
  const lower = path.toLowerCase();
  if (lower.endsWith(".pdf")) return "application/pdf";
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  if (lower.endsWith(".webp")) return "image/webp";
  return "application/octet-stream";
}
