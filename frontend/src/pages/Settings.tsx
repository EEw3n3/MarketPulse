import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Moon, Sun, Check, LogOut, Trash2, Camera, ArrowLeft, User, Sliders, Bell, Palette, ShieldAlert } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
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
          <Card className="mb-6 bg-surface-2/30 backdrop-blur-md border-border">
            <CardHeader className="pb-4 border-b border-border/50">
              <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
                <User className="w-4 h-4 text-primary" /> Profile
              </CardTitle>
              <CardDescription className="text-xs">Manage your personal details and account security.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5 pt-5">
              <div className="flex items-center gap-5">
                <div className="relative group cursor-pointer">
                  <div className="w-16 h-16 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xl font-bold shrink-0 ring-2 ring-primary/20 ring-offset-2 ring-offset-background group-hover:ring-primary/40 transition-all duration-300">
                    E
                  </div>
                  <div className="absolute inset-0 bg-black/40 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <Camera className="w-5 h-5 text-white" />
                  </div>
                </div>
                <div>
                  <button className="text-[13px] font-medium text-primary hover:text-primary/80 transition-colors">
                    Upload new picture
                  </button>
                  <p className="text-[11px] text-muted-foreground mt-0.5">JPG, GIF or PNG. Max size 2MB.</p>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-[12px] font-medium text-foreground">Name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} className="bg-surface border-border focus-visible:ring-primary/30 focus-visible:border-primary/50 transition-all h-9 text-sm" />
              </div>

              <div className="space-y-1.5">
                <label className="text-[12px] font-medium text-foreground">Email</label>
                <div className="relative">
                  <Input value="ervin@example.com" disabled className="bg-surface border-border pr-20 opacity-70 h-9 text-sm" />
                  <Badge className="absolute right-2 top-1/2 -translate-y-1/2 bg-[hsl(var(--success))]/15 text-[hsl(var(--success))] border-[hsl(var(--success))]/30 text-[10px] px-1.5">Verified</Badge>
                </div>
              </div>

              <div className="pt-2">
                <button onClick={() => setShowPasswordFields(!showPasswordFields)} className="text-[13px] font-medium text-primary hover:text-primary/80 transition-colors">
                  {showPasswordFields ? "Cancel" : "Change Password"}
                </button>
              </div>

              {showPasswordFields && (
                <div className="space-y-3 animate-fade-in p-4 bg-surface-2/30 rounded-[var(--radius-card)] border border-border/50">
                  <Input type="password" placeholder="Current password" className="bg-surface border-border focus-visible:ring-primary/30 focus-visible:border-primary/50 h-9 text-sm" />
                  <Input type="password" placeholder="New password" className="bg-surface border-border focus-visible:ring-primary/30 focus-visible:border-primary/50 h-9 text-sm" />
                  <Input type="password" placeholder="Confirm new password" className="bg-surface border-border focus-visible:ring-primary/30 focus-visible:border-primary/50 h-9 text-sm" />
                </div>
              )}

              <Button className="w-full btn-primary h-9 shadow-glow hover:scale-[1.01] transition-transform">Save Changes</Button>
            </CardContent>
          </Card>

          {/* ── 2. Preferences ─────────────────────────────── */}
          <Card className="mb-6 bg-surface-2/30 backdrop-blur-md border-border">
            <CardHeader className="pb-4 border-b border-border/50">
              <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Sliders className="w-4 h-4 text-primary" /> Personalization
              </CardTitle>
              <CardDescription className="text-xs">Select your priority stores and brands for the dashboard.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6 pt-5">
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
            </CardContent>
          </Card>

          {/* ── 3. Notifications ───────────────────────────── */}
          <Card className="mb-6 bg-surface-2/30 backdrop-blur-md border-border">
            <CardHeader className="pb-4 border-b border-border/50">
              <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Bell className="w-4 h-4 text-primary" /> Notifications
              </CardTitle>
              <CardDescription className="text-xs">Configure how and when you receive price alerts.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-5">
            <div className="space-y-4">
              <NotifRow label="Price drop alerts" description="Immediate notification when a tracked product drops in price." checked={priceDropAlerts} onChange={setPriceDropAlerts} />
              <NotifRow label="Price increase alerts" description="Daily digest of price increases." checked={priceIncreaseAlerts} onChange={setPriceIncreaseAlerts} />
              <NotifRow label="New products in my brands" description="Alert when a new product from your favorite brands appears." checked={newProductAlerts} onChange={setNewProductAlerts} />
              <NotifRow label="Weekly email digest" description="Summary report sent every Monday." checked={weeklyDigest} onChange={setWeeklyDigest} />
            </div>
            
            <Separator className="my-2 border-border/50" />
            
            <div className="space-y-2">
              <label className="text-[12px] font-medium text-foreground">Sensitivy Threshold</label>
              <p className="text-[11px] text-muted-foreground mb-1.5">Minimum price change required to trigger an alert.</p>
              <Select value={minChange} onValueChange={setMinChange}>
                <SelectTrigger className="bg-surface border-border focus-visible:ring-primary/30 h-9 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-surface border-border">
                  <SelectItem value="3">3% (High sensitivity)</SelectItem>
                  <SelectItem value="5">5% (Recommended)</SelectItem>
                  <SelectItem value="10">10% (Medium)</SelectItem>
                  <SelectItem value="20">20% (Major drops only)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            </CardContent>
          </Card>

          {/* ── 4. Appearance ──────────────────────────────── */}
          <Card className="mb-6 bg-surface-2/30 backdrop-blur-md border-border">
            <CardHeader className="pb-4 border-b border-border/50">
              <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Palette className="w-4 h-4 text-primary" /> Appearance
              </CardTitle>
              <CardDescription className="text-xs">Customize the interface visual theme.</CardDescription>
            </CardHeader>
            <CardContent className="pt-5">
              <div className="flex items-center bg-surface border border-border rounded-full p-1 gap-1 w-fit">
                <button
                  onClick={() => { if (!isDark) toggleTheme(); }}
                  className={`flex items-center gap-2 px-5 py-2 rounded-full text-[13px] font-medium transition-all duration-300 ${
                    isDark ? "bg-primary text-primary-foreground shadow-glow" : "text-muted-foreground hover:text-foreground hover:bg-surface-2"
                  }`}
                >
                  <Moon className="w-4 h-4" /> Dark
                </button>
                <button
                  onClick={() => { if (isDark) toggleTheme(); }}
                  className={`flex items-center gap-2 px-5 py-2 rounded-full text-[13px] font-medium transition-all duration-300 ${
                    !isDark ? "bg-primary text-primary-foreground shadow-glow" : "text-muted-foreground hover:text-foreground hover:bg-surface-2"
                  }`}
                >
                  <Sun className="w-4 h-4" /> Light
                </button>
              </div>
            </CardContent>
          </Card>

          {/* ── 5. Account ─────────────────────────────────── */}
          <Card className="mb-10 bg-destructive/[0.02] border-destructive/20 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-destructive/10 rounded-full blur-[40px] -translate-y-1/2 translate-x-1/2 pointer-events-none" />
            <CardHeader className="pb-4 border-b border-destructive/10">
              <CardTitle className="text-sm font-semibold text-destructive flex items-center gap-2">
                <ShieldAlert className="w-4 h-4" /> Danger Zone
              </CardTitle>
              <CardDescription className="text-xs">Irreversible and destructive actions.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-5 relative z-10">
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
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}

function NotifRow({ label, description, checked, onChange }: { label: string; description: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-[13px] font-medium text-foreground">{label}</p>
        <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed pr-6">{description}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} className="data-[state=checked]:bg-primary mt-1" />
    </div>
  );
}
