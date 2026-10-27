import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useT } from "@/i18n";

export function PageLoading() {
  const t = useT();
  return (
    <div className="boot" role="status">
      <span className="logo">MarketPulse</span>
      <span className="sr">{t.common.loading}</span>
    </div>
  );
}

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const { pathname, search, hash } = useLocation();
  if (loading) return <PageLoading />;
  if (!user) return <Navigate to={`/signin?next=${encodeURIComponent(pathname + search + hash)}`} replace />;
  return <>{children}</>;
}
