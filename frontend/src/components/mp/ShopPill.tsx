import { fieldStyle, shopOf } from "@/lib/shops";

export default function ShopPill({ store, dot = false }: { store: string; dot?: boolean }) {
  return (
    <span className="pill" style={fieldStyle(store)}>
      {dot && <i />}
      {shopOf(store).label}
    </span>
  );
}
