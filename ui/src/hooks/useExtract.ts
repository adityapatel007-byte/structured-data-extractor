/**
 * useExtract — manages the upload → API → result lifecycle for a single call.
 *
 * Deliberately simple: no react-query, no cache, no retry. One call at a time,
 * cancellable via `reset()`. That matches the actual UX — upload one doc, look
 * at the result, upload another.
 */
import { useCallback, useState } from "react";

import { APIError, extract, type ExtractArgs } from "@/lib/api";
import type { ExtractResponse } from "@/types";

type Status = "idle" | "loading" | "success" | "error";

export interface UseExtractState {
  status: Status;
  response: ExtractResponse | null;
  error: APIError | null;
  file: File | null;
}

export function useExtract() {
  const [state, setState] = useState<UseExtractState>({
    status: "idle",
    response: null,
    error: null,
    file: null,
  });

  const run = useCallback(async (args: ExtractArgs) => {
    setState({ status: "loading", response: null, error: null, file: args.file });
    try {
      const response = await extract(args);
      setState({ status: "success", response, error: null, file: args.file });
    } catch (err) {
      const apiErr =
        err instanceof APIError
          ? err
          : new APIError({
              code: "network_error",
              message: err instanceof Error ? err.message : "Unknown error",
            });
      setState({ status: "error", response: null, error: apiErr, file: args.file });
    }
  }, []);

  const reset = useCallback(() => {
    setState({ status: "idle", response: null, error: null, file: null });
  }, []);

  return { ...state, run, reset };
}
