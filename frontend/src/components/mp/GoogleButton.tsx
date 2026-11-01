import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useI18n } from "@/i18n";
import { api } from "@/lib/api";

// Google Identity Services: the official "Sign in with Google" button. Google
// gives the browser a signed ID token; /auth/google checks it on the server.
interface Gis {
  accounts: {
    id: {
      initialize: (o: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: "popup"; context?: string }) => void;
      renderButton: (el: HTMLElement, o: Record<string, string | number>) => void;
    };
  };
}
declare global {
  interface Window {
    google?: Gis;
  }
}

let loading: Promise<void> | null = null;
function loadGis(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  loading ??= new Promise<void>((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => {
      loading = null;
      reject(new Error("Google script not loaded"));
    };
    document.head.appendChild(s);
  });
  return loading;
}

/** Renders nothing until the server has a Google client ID (GOOGLE_CLIENT_ID in .env). */
export default function GoogleButton({
  mode,
  orText,
  onCredential,
}: {
  mode: "signin" | "register";
  /** The divider between the button and the e-mail form. */
  orText: string;
  onCredential: (credential: string) => void;
}) {
  const { lang } = useI18n();
  const ref = useRef<HTMLDivElement>(null);
  const cb = useRef(onCredential);
  cb.current = onCredential;
  const { data } = useQuery({ queryKey: ["google-config"], queryFn: api.googleConfig, staleTime: Infinity, retry: false });
  const clientId = data?.client_id;

  useEffect(() => {
    if (!clientId) return;
    let gone = false;
    loadGis()
      .then(() => {
        const el = ref.current;
        if (gone || !el || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (r) => cb.current(r.credential),
          ux_mode: "popup",
          context: mode === "register" ? "signup" : "signin",
        });
        el.innerHTML = "";
        window.google.accounts.id.renderButton(el, {
          type: "standard",
          theme: "outline",
          size: "large",
          shape: "pill",
          text: mode === "register" ? "signup_with" : "signin_with",
          logo_alignment: "center",
          locale: lang,
          width: Math.max(200, Math.min(400, el.clientWidth || 320)),
        });
      })
      .catch(() => undefined);
    return () => {
      gone = true;
    };
  }, [clientId, lang, mode]);

  if (!clientId) return null;
  return (
    <>
      <div className="gbtn" ref={ref} />
      <div className="or" aria-hidden="true">
        <span>{orText}</span>
      </div>
    </>
  );
}
