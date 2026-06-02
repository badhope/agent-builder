import { type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/utils/format";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function Card({ children, className, ...rest }: CardProps) {
  return (
    <div className={cn("card", className)} {...rest}>
      {children}
    </div>
  );
}

export default Card;