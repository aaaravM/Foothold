"use client";

import * as React from "react";

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return true;
  return target.closest('[contenteditable=""], [contenteditable="true"], [role="textbox"], [role="combobox"]') !== null;
}

/**
 * The page's 4 / 8 / 12-column technical grid as a hairline overlay (same columns as the
 * `page-grid` utility). Faint behind the content by default; press G to show it over
 * everything like a design tool, G again to fade it back. G is ignored while typing or
 * with a modifier key. Rendered once by app/layout.tsx.
 */
export function GridOverlay() {
  const [on, setOn] = React.useState(false);

  React.useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key !== "g" && e.key !== "G") return;
      if (isTypingTarget(e.target)) return;
      setOn((v) => !v);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <>
      <div aria-hidden="true" className="fh-grid-overlay" data-state={on ? "on" : "faint"}>
        <div className="page-container h-full">
          <div className="page-grid h-full">
            {Array.from({ length: 12 }, (_, i) => (
              <div key={i} className="fh-grid-col">
                <span className="fh-grid-num label-mono">{String(i + 1).padStart(2, "0")}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      {on ? (
        <p
          role="status"
          className="label-mono fixed bottom-4 left-4 z-[56] border border-accent bg-background px-2 py-1 text-accent"
        >
          Grid on · press G to hide
        </p>
      ) : null}
    </>
  );
}
