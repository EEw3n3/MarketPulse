import { useT } from "@/i18n";
import { clock, day, hoursSince, isToday } from "@/lib/format";

/** Prices older than this are "data from …": the PC that scrapes Notino and
 * 220.lv skipped a night (same limit as the server, app/services/freshness.py). */
export const STALE_HOURS = 30;

/** "checked today at 09:40", "checked 30 Oct", or "data from 29 Oct" when the
 * shop's price is older than STALE_HOURS. */
export default function Checked({ at, className = "" }: { at?: string | null; className?: string }) {
  const t = useT();
  if (!at) return null;
  const stale = (hoursSince(at) ?? 0) > STALE_HOURS;
  const text = stale ? t.common.staleData(day(at)) : isToday(at) ? t.common.checkedToday(clock(at)) : t.common.checkedOn(day(at));
  return <small className={`checked ${stale ? "stale" : ""} ${className}`.trim()}>{text}</small>;
}
