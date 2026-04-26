import { cn } from "@/lib/utils";

interface TocSection {
  id: string;
  index: string;
  label: string;
}

interface Props {
  sections: TocSection[];
  active: string;
}

export default function AnalyticsToc({ sections, active }: Props) {
  const handleClick = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <aside className="hidden lg:block w-[200px] shrink-0 sticky top-0 self-start py-7 pl-7 pr-4 h-screen overflow-hidden">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground mb-5">
        · Sections
      </p>
      <nav className="flex flex-col">
        {sections.map((s) => {
          const isActive = active === s.id;
          return (
            <a
              key={s.id}
              href={`#${s.id}`}
              onClick={(e) => handleClick(e, s.id)}
              className={cn(
                "group relative flex items-baseline gap-2.5 py-2 pl-3 -ml-3 transition-colors",
                isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <span
                className={cn(
                  "absolute left-0 top-1/2 -translate-y-1/2 w-[2px] rounded-r transition-all",
                  isActive ? "h-4 bg-primary" : "h-0 bg-transparent"
                )}
              />
              <span className="font-mono text-[10px] tabular-nums w-5 shrink-0 text-muted-foreground/70">
                {s.index}
              </span>
              <span className="text-[12.5px] tracking-[-0.005em] font-medium">{s.label}</span>
            </a>
          );
        })}
      </nav>
    </aside>
  );
}
