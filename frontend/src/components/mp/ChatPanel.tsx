import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowUp, X } from "lucide-react";
import { api, type ChatMessage } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useChat } from "@/contexts/ChatContext";
import { useT } from "@/i18n";

const MAX_STORED = 40;

/** The assistant ends a reply with "→ Option? | Option? | Option?". */
function splitReply(text: string): { body: string; chips: string[] } {
  const lines = text.trim().split("\n");
  const last = lines[lines.length - 1]?.trim() ?? "";
  if (last.startsWith("→")) {
    const chips = last
      .replace(/^→\s*/, "")
      .split("|")
      .map((s) => s.trim().replace(/^['"“]|['"”]$/g, ""))
      .filter(Boolean)
      .slice(0, 3);
    return { body: lines.slice(0, -1).join("\n").trim(), chips };
  }
  return { body: text.trim(), chips: [] };
}

/** **bold** and bare links; everything else stays plain text. */
function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|https?:\/\/[^\s)]+)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<b key={i++}>{tok.slice(2, -2)}</b>);
    else
      out.push(
        <a key={i++} href={tok} target="_blank" rel="noreferrer">
          {tok.replace(/^https?:\/\/(www\.)?/, "").slice(0, 32)}…
        </a>,
      );
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function Bubble({ m }: { m: ChatMessage }) {
  const text = m.role === "assistant" ? splitReply(m.content).body : m.content;
  return (
    <div className={`bub ${m.role === "user" ? "me" : "ai"}`}>
      {text.split("\n").map((line, i, arr) => (
        <Fragment key={i}>
          {inline(line.replace(/^\s*[-*•]\s+/, "• "))}
          {i < arr.length - 1 && "\n"}
        </Fragment>
      ))}
    </div>
  );
}

export default function ChatPanel() {
  const t = useT();
  const { user } = useAuth();
  const { open, setOpen, pageContext, pending, takePending } = useChat();
  const key = user ? `marketpulse_chat_${user.id}` : null;
  const [msgs, setMsgs] = useState<ChatMessage[]>(() => {
    if (!key) return [];
    try {
      return JSON.parse(localStorage.getItem(key) || "[]");
    } catch {
      return [];
    }
  });
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const body = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const fab = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!key) return;
    try {
      localStorage.setItem(key, JSON.stringify(msgs.slice(-MAX_STORED)));
    } catch {
      /* storage full or blocked */
    }
  }, [msgs, key]);

  useEffect(() => {
    body.current?.scrollTo({ top: body.current.scrollHeight });
  }, [msgs, busy, open]);

  useEffect(() => {
    if (open) setTimeout(() => input.current?.focus(), 30);
  }, [open]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    const history = msgs.slice(-6);
    setMsgs((m) => [...m, { role: "user", content: q }]);
    setDraft("");
    setErr(null);
    setBusy(true);
    try {
      const res = await api.sendChat(q, history, pageContext || undefined);
      setMsgs((m) => [...m, { role: "assistant", content: res.reply }]);
    } catch (e) {
      setErr(String(e).includes("429") ? t.chat.limit : t.chat.failed);
    } finally {
      setBusy(false);
    }
  }

  // A page opened the chat with a question (Today's ask bar, product page).
  useEffect(() => {
    if (open && pending) {
      const q = takePending();
      if (q) send(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, pending]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        fab.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  if (!user) return null;

  const lastAi = [...msgs].reverse().find((m) => m.role === "assistant");
  const chips = !busy && lastAi && msgs[msgs.length - 1] === lastAi ? splitReply(lastAi.content).chips : [];

  if (!open) {
    return (
      <button ref={fab} className="chat-fab" type="button" onClick={() => setOpen(true)} aria-label={t.chat.fab}>
        <i aria-hidden="true" />
        <span>{t.chat.fab}</span>
      </button>
    );
  }

  return (
    <section className="chat fade" role="dialog" aria-label={t.chat.title}>
      <div className="chat-h">
        <div>
          <b>{t.chat.title}</b>
          <small>{t.chat.sub}</small>
        </div>
        {msgs.length > 0 && (
          <button className="clr" type="button" onClick={() => { setMsgs([]); setErr(null); }} style={{ marginLeft: "auto" }}>
            {t.chat.clear}
          </button>
        )}
        <button className="x" type="button" onClick={() => setOpen(false)} aria-label={t.chat.close} style={msgs.length ? { marginLeft: 8 } : undefined}>
          <X size={18} />
        </button>
      </div>
      <div className="chat-b" ref={body} aria-live="polite">
        <div className="bub ai">{t.chat.hello}</div>
        {msgs.length === 0 && (
          <div className="chat-s">
            {t.chat.starters.map((s) => (
              <button key={s} type="button" onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => (
          <Bubble key={i} m={m} />
        ))}
        {busy && (
          <div className="bub ai" aria-label={t.chat.thinking}>
            <span className="typing" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          </div>
        )}
        {err && <p className="err">{err}</p>}
        {chips.length > 0 && (
          <div className="chat-s">
            {chips.map((s) => (
              <button key={s} type="button" onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
      <form
        className="chat-f"
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
      >
        <label className="sr" htmlFor="chat-q">
          {t.chat.placeholder}
        </label>
        <textarea
          id="chat-q"
          ref={input}
          rows={1}
          value={draft}
          placeholder={t.chat.placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(draft);
            }
          }}
        />
        <button className="btn btn-ink" type="submit" disabled={busy || !draft.trim()} aria-label={t.chat.send}>
          <ArrowUp size={18} />
        </button>
      </form>
    </section>
  );
}
