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
    throw new Error(`Failed to load sample: ${sample.path}`);
  }
  const blob = await res.blob();
  const filename = sample.path.split("/").pop() ?? "sample";
  return new File([blob], filename, { type: blob.type });
}
