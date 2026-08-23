import { cn } from "@/lib/utils";

export function Badge({
  children,
  className,
  tone = "neutral",
}: {
  children: React.ReactNode;
  className?: string;
  tone?: "neutral" | "live" | "cached" | "warn" | "fail" | "ok";
}) {
  const tones = {
    neutral: "border-line text-mist",
    live: "border-cyan/40 text-cyan",
    cached: "border-gold/40 text-gold",
    warn: "border-amber-500/40 text-amber-400",
    fail: "border-fail/40 text-fail",
    ok: "border-ok/40 text-ok",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-[0.14em]",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
