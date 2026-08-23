import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-sm text-[11px] font-medium tracking-[0.08em] uppercase transition-colors disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        default: "bg-gold text-ink hover:bg-gold/90",
        outline: "border border-line bg-transparent text-fog hover:bg-panel-2 hover:text-paper",
        ghost: "text-mist hover:bg-panel-2 hover:text-paper",
        live: "bg-cyan/15 text-cyan border border-cyan/30 hover:bg-cyan/25",
      },
      size: {
        default: "h-8 px-3",
        sm: "h-7 px-2.5",
        lg: "h-9 px-4",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = "Button";
