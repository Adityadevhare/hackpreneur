import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";

import { supabase } from "../lib/supabase";
import { AuthContext } from "./auth-context";
import type {
  AuthContextValue,
  AuthStatus,
  SignUpResult,
} from "./auth-context";

function getAuthErrorMessage(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;

    if (typeof message === "string" && message.trim()) {
      return message.trim();
    }
  }

  return "Authentication failed. Please try again.";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;
    let authEventReceived = false;

    const applySession = (nextSession: Session | null) => {
      if (!isActive) {
        return;
      }

      setSession(nextSession);
      setStatus(nextSession ? "authenticated" : "unauthenticated");
    };

    void supabase.auth
      .getSession()
      .then(({ data, error: sessionError }) => {
        if (!isActive || authEventReceived) {
          return;
        }

        if (sessionError) {
          setError(getAuthErrorMessage(sessionError));
          setSession(null);
          setStatus("unauthenticated");
          return;
        }

        applySession(data.session);
      })
      .catch((sessionError: unknown) => {
        if (!isActive || authEventReceived) {
          return;
        }

        setError(getAuthErrorMessage(sessionError));
        setSession(null);
        setStatus("unauthenticated");
      });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      authEventReceived = true;
      applySession(nextSession);
    });

    return () => {
      isActive = false;
      subscription.unsubscribe();
    };
  }, []);

  const signIn = useCallback(
    async (email: string, password: string): Promise<boolean> => {
      setError(null);

      try {
        const { error: authError } = await supabase.auth.signInWithPassword({
          email,
          password,
        });

        if (authError) {
          setError(getAuthErrorMessage(authError));
          return false;
        }

        return true;
      } catch (authError) {
        setError(getAuthErrorMessage(authError));
        return false;
      }
    },
    [],
  );

  const signUp = useCallback(
    async (email: string, password: string): Promise<SignUpResult | null> => {
      setError(null);

      try {
        const { data, error: authError } = await supabase.auth.signUp({
          email,
          password,
        });

        if (authError) {
          setError(getAuthErrorMessage(authError));
          return null;
        }

        const requiresEmailConfirmation = !data.session;

        setSession(data.session);
        setStatus(data.session ? "authenticated" : "unauthenticated");

        return { requiresEmailConfirmation };
      } catch (authError) {
        setError(getAuthErrorMessage(authError));
        return null;
      }
    },
    [],
  );

  const signOut = useCallback(async (): Promise<void> => {
    setError(null);

    try {
      const { error: authError } = await supabase.auth.signOut();

      if (authError) {
        setError(getAuthErrorMessage(authError));
        return;
      }

      setSession(null);
      setStatus("unauthenticated");
    } catch (authError) {
      setError(getAuthErrorMessage(authError));
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      session,
      user: session?.user ?? null,
      error,
      signIn,
      signUp,
      signOut,
      clearError,
    }),
    [status, session, error, signIn, signUp, signOut, clearError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
