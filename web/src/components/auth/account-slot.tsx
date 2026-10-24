import Link from "next/link";

/** Placeholder until the auth builder lands the real account menu. */
export function AccountSlot() {
  return (
    <Link href="/signin" className="label-mono text-ink-muted transition-colors hover:text-ink">
      Sign in
    </Link>
  );
}
