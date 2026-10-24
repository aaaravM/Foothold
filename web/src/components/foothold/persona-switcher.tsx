"use client";

import * as React from "react";
import { Building2, ChevronDown, UserRound } from "lucide-react";
import { cn } from "@/lib/utils";
import { isPersonaId } from "@/lib/personas";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { usePersona } from "./persona-provider";

export interface PersonaSwitcherProps {
  className?: string;
  /** hide the persona name on narrow layouts (icon + chevron only) */
  compact?: boolean;
}

/** Switch the demo persona (maya, dev, luis, Tri-Valley Freight). All fictional, and labeled so. */
export function PersonaSwitcher({ className, compact = false }: PersonaSwitcherProps) {
  const { personaId, persona, personas, setPersona, forced } = usePersona();
  const learners = personas.filter((p) => p.kind === "learner");
  const employers = personas.filter((p) => p.kind === "employer");
  const Icon = persona.kind === "employer" ? Building2 : UserRound;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          aria-label={`Persona: ${persona.name} (fictional)${forced ? ", set by demo mode" : ""}. Change persona`}
          className={cn("gap-1.5 text-ink-muted hover:text-ink", className)}
        >
          <Icon aria-hidden="true" />
          <span className={cn("label-mono max-w-[11ch] truncate text-ink", compact && "sr-only")}>{persona.name}</span>
          <ChevronDown aria-hidden="true" className="size-3.5 opacity-70" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuLabel className="label-mono text-ink-faint">Persona · all fictional</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={personaId}
          onValueChange={(v) => {
            if (isPersonaId(v)) setPersona(v);
          }}
        >
          <DropdownMenuGroup>
            <DropdownMenuLabel className="label-mono pt-2 text-ink-faint">Learners</DropdownMenuLabel>
            {learners.map((p) => (
              <DropdownMenuRadioItem key={p.id} value={p.id} className="items-start py-1.5">
                <span className="flex min-w-0 flex-col">
                  <span className="text-sm font-medium">{p.name}</span>
                  <span className="text-xs leading-snug opacity-80">{p.tagline}</span>
                </span>
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuLabel className="label-mono pt-2 text-ink-faint">Employer</DropdownMenuLabel>
            {employers.map((p) => (
              <DropdownMenuRadioItem key={p.id} value={p.id} className="items-start py-1.5">
                <span className="flex min-w-0 flex-col">
                  <span className="text-sm font-medium">{p.name}</span>
                  <span className="text-xs leading-snug opacity-80">{p.tagline}</span>
                </span>
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuGroup>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
