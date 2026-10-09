import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./client";

/** One cache per part of the site (see AuthProvider), so one account's data is never shown in another's pages. */
export function newQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        // Don't retry business errors (404/403/409...); retry network/5xx once
        retry: (count, err) => count < 1 && !(err instanceof ApiError && err.status >= 400 && err.status < 500),
      },
    },
  });
}
