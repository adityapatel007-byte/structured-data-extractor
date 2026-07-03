Drop sample documents in this folder to make them available via the
"Try a sample" buttons in the UI.

Filenames referenced by src/lib/samples.ts:
  - coffee_receipt.png
  - software_invoice.pdf

To swap in your own samples, either replace these files 1:1, or edit
SAMPLE_DOCS in src/lib/samples.ts to point at whatever you drop here.

Committed samples are optional — the UI falls back gracefully if a sample
path 404s (the button surfaces a console warning; no crash).
