# src/ui — deprecated in favor of `ui/`

Original plan for this folder was a Streamlit demo. We upgraded to a proper
React + Motion + R3F frontend that lives at the repo root under `ui/`.

Streamlit couldn't carry the Paper & Ink design language (custom fonts,
theme variables, kinetic typography, 3D scene), so we swapped stacks.

To run the UI:

```bash
cd ui
npm install
npm run dev
```

See `ui/README.md` for the full picture.
