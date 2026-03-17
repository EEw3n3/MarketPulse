import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Moon, Sun, Check, LogOut, Trash2, Camera, ArrowLeft } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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

export default function Settings() {
  const navigate = useNavigate();

  // Profile
  const [name, setName] = useState("Ervin Mihailovic");
  const [showPasswordFields, setShowPasswordFields] = useState(false);

  // Preferences
  const [trackedStores, setTrackedStores] = useState<Set<string>>(new Set(["douglas", "notino"]));
  const [favBrands, setFavBrands] = useState<Set<string>>(new Set(["Dior", "Chanel", "Tom Ford"]));

  // Notifications
  const [priceDropAlerts, setPriceDropAlerts] = useState(true);
  const [priceIncreaseAlerts, setPriceIncreaseAlerts] = useState(false);
  const [newProductAlerts, setNewProductAlerts] = useState(true);
  const [weeklyDigest, setWeeklyDigest] = useState(true);
  const [minChange, setMinChange] = useState("5");

  // Appearance
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

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <DashboardSidebar onSettingsClick={() => {}} />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[600px] mx-auto py-10 px-6 animate-fade-in">
          {/* Back */}
          <button
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-primary transition-colors mb-6"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>

          <h1 className="text-2xl font-display font-bold text-foreground mb-8">Settings</h1>

          {/* ── 1. Profile ─────────────────────────────────── */}
          <section className="space-y-4 mb-8">
            <h3 className="text-[13px] font-semibold text-muted-foreground uppercase tracking-widest">Profile</h3>

            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-primary/20 text-primary flex items-center justify-center text-xl font-bold shrink-0">E</div>
              <button className="inline-flex items-center gap-1.5 text-[13px] text-primary hover:text-primary/80 transition-colors">
                <Camera className="w-3.5 h-3.5" />
                Change Photo
              </button>
            </div>

            <div className="space-y-1.5">
              <label className="text-[13px] text-muted-foreground">Name</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} className="bg-surface-2/50 border-border" />
            </div>

            <div className="space-y-1.5">
              <label className="text-[13px] text-muted-foreground">Email</label>
              <div className="relative">
                <Input value="ervin@example.com" disabled className="bg-surface-2/50 border-border pr-20" />
                <Badge className="absolute right-2 top-1/2 -translate-y-1/2 bg-success/20 text-success border-success/30 text-[10px]">Verified</Badge>
              </div>
            </div>

            <button onClick={() => setShowPasswordFields(!showPasswordFields)} className="text-[13px] text-primary hover:text-primary/80 transition-colors">
              {showPasswordFields ? "Cancel" : "Change Password"}
            </button>

            {showPasswordFields && (
              <div className="space-y-3 animate-fade-in">
                <Input type="password" placeholder="Current password" className="bg-surface-2/50 border-border" />
                <Input type="password" placeholder="New password" className="bg-surface-2/50 border-border" />
                <Input type="password" placeholder="Confirm new password" className="bg-surface-2/50 border-border" />
              </div>
            )}

            <Button className="w-full btn-primary">Save Changes</Button>
          </section>

          <Separator className="mb-8" />

          {/* ── 2. Preferences ─────────────────────────────── */}
          <section className="space-y-4 mb-8">
            <h3 className="text-[13px] font-semibold text-muted-foreground uppercase tracking-widest">Preferences</h3>

            <div className="space-y-2.5">
              <label className="text-[13px] text-foreground font-medium">Tracked Stores</label>
              <div className="flex flex-wrap gap-2">
                {STORES.map((store) => {
                  const isSelected = trackedStores.has(store.id);
                  return (
                    <button
                      key={store.id}
                      onClick={() => toggleStore(store.id)}
                      className={`relative inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-200 ${
                        isSelected
                          ? "bg-primary/[0.08] text-foreground border-primary shadow-[0_0_12px_rgba(124,58,237,0.15)]"
                          : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground bg-transparent"
                      }`}
                    >
                      <img src={store.logo} alt={store.name} className="w-4 h-4 object-contain" />
                      {store.name}
                      {isSelected && <Check className="w-3 h-3 text-primary" />}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2.5">
              <label className="text-[13px] text-foreground font-medium">Favorite Brands</label>
              <div className="flex flex-wrap gap-2">
                {BRANDS.map((brand) => {
                  const isSelected = favBrands.has(brand);
                  return (
                    <button
                      key={brand}
                      onClick={() => toggleBrand(brand)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-200 ${
                        isSelected
                          ? "bg-primary text-primary-foreground border-primary shadow-[0_0_12px_rgba(124,58,237,0.25)]"
                          : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground bg-transparent"
                      }`}
                    >
                      {isSelected && <Check className="w-3 h-3" />}
                      {brand}
                    </button>
                  );
                })}
              </div>
            </div>
          </section>

          <Separator className="mb-8" />

          {/* ── 3. Notifications ───────────────────────────── */}
          <section className="space-y-4 mb-8">
            <h3 className="text-[13px] font-semibold text-muted-foreground uppercase tracking-widest">Notifications</h3>
            <div className="space-y-3">
              <NotifRow label="Price drop alerts" checked={priceDropAlerts} onChange={setPriceDropAlerts} />
              <NotifRow label="Price increase alerts" checked={priceIncreaseAlerts} onChange={setPriceIncreaseAlerts} />
              <NotifRow label="New products in my brands" checked={newProductAlerts} onChange={setNewProductAlerts} />
              <NotifRow label="Weekly email digest" checked={weeklyDigest} onChange={setWeeklyDigest} />
            </div>
            <div className="space-y-1.5">
              <label className="text-[13px] text-muted-foreground">Minimum price change to notify</label>
              <Select value={minChange} onValueChange={setMinChange}>
                <SelectTrigger className="bg-surface-2/50 border-border w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-surface border-border">
                  <SelectItem value="3">3%</SelectItem>
                  <SelectItem value="5">5%</SelectItem>
                  <SelectItem value="10">10%</SelectItem>
                  <SelectItem value="20">20%</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </section>

          <Separator className="mb-8" />

          {/* ── 4. Appearance ──────────────────────────────── */}
          <section className="space-y-4 mb-8">
            <h3 className="text-[13px] font-semibold text-muted-foreground uppercase tracking-widest">Appearance</h3>
            <div className="flex items-center bg-surface-2 rounded-full p-0.5 gap-0.5 w-fit">
              <button
                onClick={() => { if (!isDark) toggleTheme(); }}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-medium transition-all duration-300 ${
                  isDark ? "bg-primary text-primary-foreground" : "text-muted-foreground"
                }`}
              >
                <Moon className="w-3.5 h-3.5" /> Dark
              </button>
              <button
                onClick={() => { if (isDark) toggleTheme(); }}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-medium transition-all duration-300 ${
                  !isDark ? "bg-primary text-primary-foreground" : "text-muted-foreground"
                }`}
              >
                <Sun className="w-3.5 h-3.5" /> Light
              </button>
            </div>
          </section>

          <Separator className="mb-8" />

          {/* ── 5. Account ─────────────────────────────────── */}
          <section className="space-y-4 pb-10">
            <h3 className="text-[13px] font-semibold text-muted-foreground uppercase tracking-widest">Account</h3>
            <Button variant="outline" className="w-full border-destructive text-destructive hover:bg-destructive/10 hover:text-destructive">
              <LogOut className="w-4 h-4 mr-2" /> Sign Out
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <button className="text-[11px] text-muted-foreground underline hover:text-destructive transition-colors">Delete Account</button>
              </AlertDialogTrigger>
              <AlertDialogContent className="bg-surface border-border rounded-modal">
                <AlertDialogHeader>
                  <AlertDialogTitle className="text-foreground">Delete your account?</AlertDialogTitle>
                  <AlertDialogDescription>This action cannot be undone. All your data, tracked products, and preferences will be permanently deleted.</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel className="border-border">Cancel</AlertDialogCancel>
                  <AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                    <Trash2 className="w-4 h-4 mr-1" /> Delete Account
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </section>
        </div>
      </main>
    </div>
  );
}

function NotifRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-foreground">{label}</span>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}
