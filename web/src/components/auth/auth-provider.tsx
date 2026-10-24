"use client";

import * as React from "react";

export type AccountKind = "learner" | "employer";

export type Account = {
  id: string;
  kind: AccountKind;
  display_name: string;
  persona_id: string;
  email: string;
  initials: string;
  org?: string;
};

export type AuthState = {
  account: Account | null;
  status: "loading" | "signed_in" | "signed_out";
  token: string | null;
  signOut: () => void;
};

const SIGNED_OUT: AuthState = { account: null, status: "signed_out", token: null, signOut: () => {} };

const AuthContext = React.createContext<AuthState>(SIGNED_OUT);

/** Placeholder until the auth builder lands per-tab (sessionStorage) sessions backed by /api/auth. */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  return <AuthContext.Provider value={SIGNED_OUT}>{children}</AuthContext.Provider>;
}

export function useAccount(): AuthState {
  return React.useContext(AuthContext);
}
