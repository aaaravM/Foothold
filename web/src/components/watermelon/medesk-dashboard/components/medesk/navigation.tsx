"use client";

/*
 * Watermelon UI "medesk-dashboard" (MIT), adapted for Foothold: in-portal navigation
 * without a router, so the portal can live inside one Next.js page. Added `initialPath`.
 */
import {
  createContext,
  useContext,
  useMemo,
  useState,
  type AnchorHTMLAttributes,
  type MouseEvent,
  type ReactNode,
} from "react";

type DashboardNavigation = {
  pathname: string;
  navigate: (pathname: string) => void;
};

const DashboardNavigationContext = createContext<DashboardNavigation | null>(
  null,
);

export function DashboardNavigationProvider({
  children,
  initialPath = "/",
}: {
  children: ReactNode;
  initialPath?: string;
}) {
  const [pathname, setPathname] = useState(initialPath);
  const value = useMemo(
    () => ({ pathname, navigate: setPathname }),
    [pathname],
  );

  return (
    <DashboardNavigationContext.Provider value={value}>
      {children}
    </DashboardNavigationContext.Provider>
  );
}

export function useDashboardNavigation() {
  const context = useContext(DashboardNavigationContext);

  if (!context) {
    throw new Error(
      "useDashboardNavigation must be used within DashboardNavigationProvider",
    );
  }

  return context;
}

export function DashboardLink({
  href,
  onClick,
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  const { navigate } = useDashboardNavigation();

  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);

    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }

    event.preventDefault();
    navigate(href);
  }

  return <a href={`#portal${href === "/" ? "" : href}`} onClick={handleClick} {...props} />;
}
