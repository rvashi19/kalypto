import { useMutation } from "@tanstack/react-query";

import { api } from "./api";
import { useAuth } from "./use-auth";

/** Revokes the session on the server (best effort) and always clears it locally. */
export function useLogout() {
  const { token, setSession } = useAuth();
  return useMutation({
    mutationFn: async () => {
      if (token) await api.logout(token);
    },
    onSettled: () => setSession(null),
  });
}
