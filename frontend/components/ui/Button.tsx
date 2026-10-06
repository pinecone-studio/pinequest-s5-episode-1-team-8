import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost";
  size?: "md" | "lg";
};

const VARIANTS = {
  primary: "border-brand bg-brand text-[#07130c] hover:border-brand-2 hover:bg-brand-2",
  ghost: "border-line-2 bg-transparent text-fg hover:border-brand",
};
const SIZES = { md: "px-4 py-[9px] text-sm", lg: "px-[26px] py-[15px] text-base" };

export function Button({ variant = "ghost", size = "md", className = "", ...props }: Props) {
  return (
    <button
      className={`inline-flex cursor-pointer items-center justify-center gap-2 rounded-[10px] border-[1.5px] font-semibold transition-colors disabled:cursor-default disabled:opacity-45 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    />
  );
}
