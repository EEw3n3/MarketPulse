import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Moon, Sun, Check, LogOut, Trash2, ArrowLeft } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import DashboardSidebar from "@/components/dashboard/DashboardSidebar";
import { cn } from "@/lib/utils";

import storeDouglas from "@/assets/store-douglas.png";
import storeNotino from "@/assets/store-notino.png";
import store220 from "@/assets/store-220.png";
import storeMakeup from "@/assets/store-makeup.png";
import store1a from "@/assets/store-1a.png";

const STORES = [
  { id: "douglas", name: "Douglas.lv", logo: storeDouglas },
  { id: "notino", name: "Notino.lv", logo: storeNotino },
  { id: "220", name: "220.lv", logo: store220 },
  { id: "makeup", name: "Makeup.lv", logo: storeMakeup },
  { id: "1a", name: "1a.lv", logo: store1a },
];

const BRANDS = [
  "Dior", "Chanel", "Tom Ford", "Versace", "Hugo Boss", "Armani",
  "Paco Rabanne", "Jean Paul Gaultier", "Creed", "YSL",
  "Burberry", "Dolce & Gabbana", "Guerlain", "Givenchy",
];

function SectionHeader({ index, label, title, description }: { index: string; label: string; title: string; description?: string }) {
  return (
    <div className="flex flex-col gap-1.5 mb-5">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
        {index} · {label}
      </p>
      <h2 className="font-['Inter'] font-semibold text-foreground text-[16px] tracking-[-0.005em]">
        {title}
      </h2>
      {description && <p className="text-[12.5px] text-muted-foreground">{description}</p>}
    </div>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
      {children}
    </span>
  );
}

const baseInput =
  "w-full h-9 px-3 rounded-md bg-surface border border-border text-[13px] text-foreground placeholder:text-muted-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors";

export default function Settings() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const [name, setName] = useState(user?.full_name ?? "");
  const [showPasswordFields, setShowPasswordFields] = useState(false);

  const [trackedStores, setTrackedStores] = useState<Set<string>>(new Set(["douglas", "notino"]));
  const [favBrands, setFavBrands] = useState<Set<string>>(new Set(["Dior", "Chanel", "Tom Ford"]));

  const [priceDropAlerts, setPriceDropAlerts] = useState(true);
  const [priceIncreaseAlerts, setPriceIncreaseAlerts] = useState(false);
  const [newProductAlerts, setNewProductAlerts] = useState(true);
  const [weeklyDigest, setWeeklyDigest] = useState(true);
  const [minChange, setMinChange] = useState("5");

  const [isDark, setIsDark] = useState(!document.documentElement.classList.contains("light"));

  const toggleStore = (id: string) => {
    setTrackedStores((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleBrand = (brand: string) => {
    setFavBrands((prev) => {
      const next = new Set(prev);
      next.has(brand) ? next.delete(brand) : next.add(brand);
      return next;
    });
  };

  const toggleTheme = () => {
    document.documentElement.classList.toggle("light");
    setIsDark(!isDark);
  };

  const initial = (user?.full_name?.[0] ?? user?.email?.[0] ?? "?").toUpperCase();
  const email = user?.email ?? "";

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <DashboardSidebar onSettingsClick={() => {}} />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[720px] mx-auto py-10 px-6">
          {/* Back */}
          <button
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground transition-colors mb-6"
          >
            <ArrowLeft size={13} strokeWidth={1.75} />
            Back
          </button>

          {/* Page header */}
          <div className="mb-10 flex flex-col gap-1.5">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Account
            </p>
            <h1 className="font-['Inter'] font-semibold text-foreground text-[28px] tracking-[-0.015em]">
              Settings
            </h1>
            <p className="text-[13px] text-muted-foreground">
              Manage your profile, preferences, and notifications.
            </p>
          </div>

          {/* ── 1. Profile ──────────────────────────────────── */}
          <section className="mb-6 rounded-md border border-border bg-surface/40 p-6">
            <SectionHeader index="01" label="Identity" title="Profile" description="Your personal details." />

            <div className="flex items-center gap-4 mb-6">
              <div className="w-14 h-14 rounded-md bg-surface-2 border border-border flex items-center justify-center text-foreground text-[18px] font-medium font-['Inter']">
                {initial}
              </div>
              <div className="flex flex-col gap-0.5">
                <span className="text-[13px] text-foreground font-medium">{user?.full_name ?? email}</span>
                <span className="font-mono text-[11px] text-muted-foreground">{email}</span>
              </div>
            </div>

            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <FieldLabel>Name</FieldLabel>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className={baseInput}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <FieldLabel>Email</FieldLabel>
                <div className="relative">
                  <input
                    type="email"
                    value={email}
                    disabled
                    className={cn(baseInput, "pr-24 opacity-70 cursor-not-allowed")}
                  />
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.1em] text-[hsl(var(--success))] border border-[hsl(var(--success))]/30 bg-[hsl(var(--success))]/[0.08] px-1.5 py-0.5 rounded">
                    <Check size={10} strokeWidth={2.5} />
                    Verified
                  </span>
                </div>
              </div>

              <div>
                <button
                  onClick={() => setShowPasswordFields(!showPasswordFields)}
                  className="text-[12px] text-muted-foreground hover:text-foreground transition-colors underline underline-offset-2"
                >
                  {showPasswordFields ? "Cancel password change" : "Change password"}
                </button>
              </div>

              {showPasswordFields && (
                <div className="flex flex-col gap-2 p-4 rounded-md bg-surface border border-border">
                  <input type="password" placeholder="Current password" className={baseInput} />
                  <input type="password" placeholder="New password" className={baseInput} />
                  <input type="password" placeholder="Confirm new password" className={baseInput} />
                </div>
              )}

              <button className="self-start h-9 px-4 rounded-md bg-foreground text-background text-[12.5px] font-medium hover:bg-foreground/90 transition-colors">
                Save changes
              </button>
            </div>
          </section>

          {/* ── 2. Preferences ──────────────────────────────── */}
          <section className="mb-6 rounded-md border border-border bg-surface/40 p-6">
            <SectionHeader
              index="02"
              label="Personalization"
              title="Tracked sources"
              description="Pick the stores and brands surfaced on your dashboard."
            />

            <div className="flex flex-col gap-2.5 mb-6">
              <FieldLabel>Stores</FieldLabel>
              <div className="flex flex-wrap gap-1.5">
                {STORES.map((store) => {
                  const isSelected = trackedStores.has(store.id);
                  return (
                    <button
                      key={store.id}
                      onClick={() => toggleStore(store.id)}
                      className={cn(
                        "inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-[12px] font-medium border transition-colors whitespace-nowrap",
                        isSelected
                          ? "bg-foreground text-background border-foreground"
                          : "bg-transparent text-muted-foreground border-border hover:text-foreground hover:border-muted-foreground"
                      )}
                    >
                      <img src={store.logo} alt={store.name} className="w-3.5 h-3.5 object-contain" />
                      {store.name}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex flex-col gap-2.5">
              <FieldLabel>Brands</FieldLabel>
              <div className="flex flex-wrap gap-1.5">
                {BRANDS.map((brand) => {
                  const isSelected = favBrands.has(brand);
                  return (
                    <button
                      key={brand}
                      onClick={() => toggleBrand(brand)}
                      className={cn(
                        "inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-[12px] font-medium border transition-colors whitespace-nowrap",
                        isSelected
                          ? "bg-surface text-foreground border-primary/60"
                          : "bg-transparent text-muted-foreground border-border hover:text-foreground hover:border-muted-foreground"
                      )}
                    >
                      {isSelected && <span className="w-1 h-1 rounded-full bg-primary" />}
                      {brand}
                    </button>
                  );
                })}
              </div>
            </div>
          </section>

          {/* ── 3. Notifications ────────────────────────────── */}
          <section className="mb-6 rounded-md border border-border bg-surface/40 p-6">
            <SectionHeader
              index="03"
              label="Alerts"
              title="Notifications"
              description="When MarketPulse should reach out to you."
            />

            <div className="flex flex-col divide-y divide-border">
              <NotifRow label="Price drop alerts" description="Immediate notification when a tracked product drops in price." checked={priceDropAlerts} onChange={setPriceDropAlerts} />
              <NotifRow label="Price increase alerts" description="Daily digest of price increases." checked={priceIncreaseAlerts} onChange={setPriceIncreaseAlerts} />
              <NotifRow label="New products in your brands" description="Alert when a new product from your favorite brands appears." checked={newProductAlerts} onChange={setNewProductAlerts} />
              <NotifRow label="Weekly email digest" description="Summary report sent every Monday." checked={weeklyDigest} onChange={setWeeklyDigest} />
            </div>

            <div className="flex flex-col gap-1.5 mt-6 pt-6 border-t border-border">
              <FieldLabel>Sensitivity threshold</FieldLabel>
              <p className="text-[11.5px] text-muted-foreground -mt-0.5 mb-1">
                Minimum price change required to trigger an alert.
              </p>
              <Select value={minChange} onValueChange={setMinChange}>
                <SelectTrigger className="bg-surface border-border h-9 text-[13px] focus:ring-1 focus:ring-primary focus:border-primary max-w-[280px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-background border-border">
                  <SelectItem value="3">3% — high sensitivity</SelectItem>
                  <SelectItem value="5">5% — recommended</SelectItem>
                  <SelectItem value="10">10% — medium</SelectItem>
                  <SelectItem value="20">20% — major drops only</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </section>

          {/* ── 4. Appearance ───────────────────────────────── */}
          <section className="mb-6 rounded-md border border-border bg-surface/40 p-6">
            <SectionHeader index="04" label="Theme" title="Appearance" />

            <div className="flex items-center gap-1 p-0.5 rounded-md border border-border bg-surface w-fit">
              <button
                onClick={() => { if (!isDark) toggleTheme(); }}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded font-mono text-[11px] uppercase tracking-[0.1em] transition-colors",
                  isDark ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Moon size={12} /> Dark
              </button>
              <button
                onClick={() => { if (isDark) toggleTheme(); }}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded font-mono text-[11px] uppercase tracking-[0.1em] transition-colors",
                  !isDark ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Sun size={12} /> Light
              </button>
            </div>
          </section>

          {/* ── 5. Account / Danger ─────────────────────────── */}
          <section className="mb-12 rounded-md border border-destructive/30 bg-destructive/[0.03] p-6">
            <SectionHeader
              index="05"
              label="Danger zone"
              title="Sign out & account"
              description="Irreversible actions affecting your account."
            />

            <div className="flex flex-col gap-3">
              <button
                onClick={() => { logout(); navigate("/"); }}
                className="w-full h-10 rounded-md border border-border text-foreground text-[12.5px] font-medium flex items-center justify-center gap-2 hover:bg-surface transition-colors"
              >
                <LogOut size={14} strokeWidth={1.75} />
                Sign out
              </button>

              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <button className="w-full h-10 rounded-md border border-destructive/40 text-destructive text-[12.5px] font-medium flex items-center justify-center gap-2 hover:bg-destructive/[0.08] transition-colors">
                    <Trash2 size={14} strokeWidth={1.75} />
                    Delete account
                  </button>
                </AlertDialogTrigger>
                <AlertDialogContent className="bg-background border border-border rounded-md">
                  <AlertDialogHeader>
                    <AlertDialogTitle className="font-['Inter'] font-semibold text-foreground text-[16px] tracking-[-0.005em]">
                      Delete your account?
                    </AlertDialogTitle>
                    <AlertDialogDescription className="text-[13px] text-muted-foreground">
                      This action cannot be undone. All your data, tracked products, and preferences
                      will be permanently deleted.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel className="border-border bg-transparent text-muted-foreground hover:text-foreground hover:bg-surface text-[12.5px]">
                      Cancel
                    </AlertDialogCancel>
                    <AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive/90 text-[12.5px]">
                      <Trash2 size={13} className="mr-1" /> Delete account
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

function NotifRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-4 first:pt-0 last:pb-0">
      <div className="min-w-0">
        <p className="text-[13px] text-foreground font-medium">{label}</p>
        <p className="text-[11.5px] text-muted-foreground mt-0.5 leading-relaxed pr-6">
          {description}
        </p>
      </div>
      <Switch
        checked={checked}
        onCheckedChange={onChange}
        className="data-[state=checked]:bg-primary mt-0.5 shrink-0"
      />
    </div>
  );
}
