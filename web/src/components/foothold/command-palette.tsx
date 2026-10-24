"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Building2, Clapperboard, Moon, Sun, UserRound } from "lucide-react";
import { NAV_SHEETS, SHEETS } from "@/lib/sheets";
import { THEME_LABELS, THEMES } from "@/lib/theme";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { usePersona } from "./persona-provider";
import { useTheme } from "./theme-toggle";

interface CommandPaletteContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
}

const CommandPaletteContext = React.createContext<CommandPaletteContextValue | null>(null);

/** Open/close the ⌘K palette from anywhere (e.g. the nav hint button). */
export function useCommandPalette(): CommandPaletteContextValue {
  const ctx = React.useContext(CommandPaletteContext);
  if (!ctx) throw new Error("useCommandPalette must be used inside <CommandPaletteProvider>");
  return ctx;
}

/** Provides the palette state, the ⌘K / Ctrl+K shortcut, and renders the palette once. */
export function CommandPaletteProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const toggle = React.useCallback(() => setOpen((o) => !o), []);

  React.useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const value = React.useMemo(() => ({ open, setOpen, toggle }), [open, toggle]);

  return (
    <CommandPaletteContext.Provider value={value}>
      {children}
      <CommandPalette open={open} onOpenChange={setOpen} />
    </CommandPaletteContext.Provider>
  );
}

const ITEM_CLASS =
  "gap-3 data-selected:bg-accent data-selected:text-accent-foreground data-selected:*:[svg]:text-accent-foreground";

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** ⌘K palette: Sheets (navigate), Persona, Theme, Demo. */
export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();
  const { personaId, personas, setPersona } = usePersona();
  const { theme, setTheme } = useTheme();
  const cover = SHEETS.find((s) => s.id === "home");
  const sheets = cover ? [cover, ...NAV_SHEETS] : NAV_SHEETS;

  const runAndClose = (fn: () => void) => {
    onOpenChange(false);
    fn();
  };

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Command palette"
      description="Jump to a sheet, switch persona or theme, or start the demo."
      className="sm:max-w-xl"
    >
      <Command loop>
        <CommandInput placeholder="Type a sheet, persona or command…" />
        <CommandList className="max-h-[min(60vh,26rem)]">
          <CommandEmpty>No match. Try “sim”, “paper” or “demo”.</CommandEmpty>

          <CommandGroup heading="Sheets">
            {sheets.map((s) => (
              <CommandItem
                key={s.id}
                value={`${s.sheet} ${s.title}`}
                keywords={[s.code, s.dwg, s.description]}
                onSelect={() => runAndClose(() => router.push(s.href))}
                className={ITEM_CLASS}
              >
                <span className="label-mono w-9 shrink-0 opacity-80">{s.sheet}</span>
                <span className="font-medium">{s.title}</span>
                <span className="hidden truncate text-xs opacity-80 sm:inline">{s.description}</span>
              </CommandItem>
            ))}
          </CommandGroup>

          <CommandSeparator />

          <CommandGroup heading="Persona · all fictional">
            {personas.map((p) => {
              const Icon = p.kind === "employer" ? Building2 : UserRound;
              return (
                <CommandItem
                  key={p.id}
                  value={`persona ${p.name}`}
                  keywords={[p.id, p.kind, p.tagline]}
                  data-checked={personaId === p.id}
                  onSelect={() => runAndClose(() => setPersona(p.id))}
                  className={ITEM_CLASS}
                >
                  <Icon aria-hidden="true" />
                  <span className="font-medium">{p.name}</span>
                  <span className="hidden truncate text-xs opacity-80 sm:inline">{p.kind === "employer" ? "Employer" : p.facts[0]}</span>
                </CommandItem>
              );
            })}
          </CommandGroup>

          <CommandSeparator />

          <CommandGroup heading="Theme">
            {THEMES.map((t) => (
              <CommandItem
                key={t}
                value={`theme ${THEME_LABELS[t]}`}
                keywords={[t, t === "light" ? "light" : "night"]}
                data-checked={theme === t}
                onSelect={() => runAndClose(() => setTheme(t))}
                className={ITEM_CLASS}
              >
                {t === "dark" ? <Moon aria-hidden="true" /> : <Sun aria-hidden="true" />}
                <span className="font-medium">{THEME_LABELS[t]}</span>
              </CommandItem>
            ))}
          </CommandGroup>

          <CommandSeparator />

          <CommandGroup heading="Demo">
            <CommandItem
              value="Start demo mode"
              keywords={["demo", "tour", "guided", "presentation"]}
              onSelect={() => runAndClose(() => router.push("/demo"))}
              className={ITEM_CLASS}
            >
              <Clapperboard aria-hidden="true" />
              <span className="font-medium">Start demo mode</span>
            </CommandItem>
          </CommandGroup>
        </CommandList>
        <div aria-hidden="true" className="label-mono flex flex-wrap gap-x-4 gap-y-1 border-t border-line px-3 py-2 text-ink-faint">
          <span>↑↓ move</span>
          <span>↵ select</span>
          <span>esc close</span>
        </div>
      </Command>
    </CommandDialog>
  );
}
