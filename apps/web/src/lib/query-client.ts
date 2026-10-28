import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      // Avoid refetching everything on each route change; mutations invalidate their own keys.
      staleTime: 30_000,
    },
  },
});
