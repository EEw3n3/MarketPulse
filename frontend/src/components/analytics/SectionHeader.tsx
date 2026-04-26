import { ReactNode } from "react";

interface Props {
  index: string;
  label: string;
  title: string;
  description?: string;
  right?: ReactNode;
}

export default function SectionHeader({ index, label, title, description, right }: Props) {
  return (
    <div className="flex items-end justify-between gap-3 flex-wrap mb-6">
      <div className="min-w-0">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
          {index} · {label}
        </p>
        <h2 className="font-['Inter'] font-semibold text-foreground text-[22px] tracking-[-0.01em]">
          {title}
        </h2>
        {description && (
          <p className="text-[13px] text-muted-foreground mt-1.5 max-w-xl">{description}</p>
        )}
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  );
}
