"use client";

import { Button } from "@/components/ui/button";

export function SearchBar({
  query,
  onQuery,
  onTrace,
  busy,
}: {
  query: string;
  onQuery: (value: string) => void;
  onTrace: () => void;
  busy: boolean;
}) {
  return (
    <div className="border-b border-line px-4 py-3">
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          onTrace();
        }}
      >
        <input
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Indonesia nickel EV supply chain"
          className="h-9 flex-1 rounded-sm border border-line bg-void px-3 font-mono text-[13px] text-paper outline-none placeholder:text-mist/70 focus:border-gold/50"
        />
        <Button type="submit" size="lg" disabled={busy}>
          {busy ? "Tracing" : "Trace"}
        </Button>
      </form>
    </div>
  );
}
