import { lazy, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { I18nProvider } from "@/i18n";
import { AuthProvider } from "@/contexts/AuthContext";
import { FavoritesProvider } from "@/contexts/FavoritesContext";
import { ChatProvider } from "@/contexts/ChatContext";
import ProtectedRoute, { PageLoading } from "@/components/auth/ProtectedRoute";
import AdminRoute from "@/components/auth/AdminRoute";
import Landing from "./pages/Landing";

const Auth = lazy(() => import("./pages/Auth"));
const OnboardingStores = lazy(() => import("./pages/Onboarding").then((m) => ({ default: m.OnboardingStores })));
const OnboardingBrands = lazy(() => import("./pages/Onboarding").then((m) => ({ default: m.OnboardingBrands })));
const Today = lazy(() => import("./pages/Today"));
const Catalog = lazy(() => import("./pages/Catalog"));
const Product = lazy(() => import("./pages/Product"));
const Favorites = lazy(() => import("./pages/Favorites"));
const Analytics = lazy(() => import("./pages/Analytics"));
const Profile = lazy(() => import("./pages/Profile"));
const AdminPanel = lazy(() => import("./pages/AdminPanel"));
const NotFound = lazy(() => import("./pages/NotFound"));

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1, staleTime: 60_000 } },
});

const guard = (el: React.ReactNode) => <ProtectedRoute>{el}</ProtectedRoute>;

const App = () => (
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <I18nProvider>
        <AuthProvider>
          <FavoritesProvider>
            <ChatProvider>
              <Toaster />
              <Suspense fallback={<PageLoading />}>
                <Routes>
                  <Route path="/" element={<Landing />} />
                  <Route path="/signin" element={<Auth mode="signin" />} />
                  <Route path="/register" element={<Auth mode="register" />} />

                  <Route path="/onboarding/stores" element={guard(<OnboardingStores />)} />
                  <Route path="/onboarding/brands" element={guard(<OnboardingBrands />)} />

                  <Route path="/today" element={guard(<Today />)} />
                  <Route path="/dashboard" element={<Navigate to="/today" replace />} />
                  <Route path="/catalog" element={guard(<Catalog />)} />
                  <Route path="/product/:id" element={guard(<Product />)} />
                  <Route path="/favorites" element={guard(<Favorites />)} />
                  <Route path="/analytics" element={guard(<Analytics />)} />
                  <Route path="/profile" element={guard(<Profile />)} />
                  <Route path="/settings" element={<Navigate to="/profile" replace />} />

                  <Route path="/admin" element={guard(<AdminRoute><AdminPanel /></AdminRoute>)} />

                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </ChatProvider>
          </FavoritesProvider>
        </AuthProvider>
      </I18nProvider>
    </BrowserRouter>
  </QueryClientProvider>
);

export default App;
