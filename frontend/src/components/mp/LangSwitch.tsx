import { useI18n, type Lang } from "@/i18n";

export default function LangSwitch({ className = "lang" }: { className?: string }) {
  const { lang, setLang, t } = useI18n();
  return (
    <div className={className} role="group" aria-label={t.shell.language}>
      {(["en", "lv"] as Lang[]).map((l) => (
        <button key={l} type="button" aria-pressed={lang === l} onClick={() => setLang(l)} lang={l}>
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
