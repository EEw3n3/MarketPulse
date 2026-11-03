// Paddle.js v2: the checkout overlay for Pro. Paddle is the reseller and
// Merchant of Record: card, VAT and receipts happen on its side; the server
// turns Pro on when Paddle's webhook arrives (app/services/billing.py).
import type { BillingConfig } from "@/lib/api";

const SRC = "https://cdn.paddle.com/paddle/v2/paddle.js";

export interface PaddleEvent {
  name?: string;
  data?: unknown;
}

interface PaddleJs {
  Environment: { set: (env: "sandbox") => void };
  Initialize: (o: { token: string; eventCallback?: (e: PaddleEvent) => void }) => void;
  Checkout: {
    open: (o: {
      items: { priceId: string; quantity: number }[];
      customer?: { email: string };
      customData?: Record<string, string>;
      settings?: Record<string, unknown>;
    }) => void;
  };
}

declare global {
  interface Window {
    Paddle?: PaddleJs;
  }
}

let loading: Promise<PaddleJs> | null = null;
let initialized: string | null = null;
let listener: ((e: PaddleEvent) => void) | null = null;

function load(): Promise<PaddleJs> {
  if (window.Paddle) return Promise.resolve(window.Paddle);
  if (!loading) {
    loading = new Promise<PaddleJs>((resolve, reject) => {
      const s = document.createElement("script");
      s.src = SRC;
      s.async = true;
      s.onload = () => (window.Paddle ? resolve(window.Paddle) : reject(new Error("Paddle.js did not start")));
      s.onerror = () => {
        loading = null;
        s.remove();
        reject(new Error("Paddle.js could not be loaded"));
      };
      document.head.appendChild(s);
    });
  }
  return loading;
}

/** Opens Paddle's checkout overlay for one price. `onEvent` gets Paddle's
 *  events ("checkout.completed", "checkout.closed", ...). */
export async function openCheckout(o: {
  config: BillingConfig;
  priceId: string;
  email: string;
  userId: number;
  onEvent: (e: PaddleEvent) => void;
}): Promise<void> {
  const token = o.config.client_token;
  if (!token) throw new Error("checkout is not available");
  const paddle = await load();
  listener = o.onEvent;
  if (initialized !== token) {
    if (o.config.environment === "sandbox") paddle.Environment.set("sandbox");
    // Initialize runs once per page; later checkouts reuse it (the listener is swapped above).
    paddle.Initialize({ token, eventCallback: (e) => listener?.(e) });
    initialized = token;
  }
  paddle.Checkout.open({
    items: [{ priceId: o.priceId, quantity: 1 }],
    customer: { email: o.email },
    // The webhook finds the MarketPulse account by this.
    customData: { user_id: String(o.userId) },
    settings: { displayMode: "overlay", theme: "light", allowLogout: false },
  });
}
