import { useState } from "react";

/** Bottle photo on a pastel field; falls back to the brand's initials. */
export default function Img({ src, brand, alt = "", className }: { src: string | null | undefined; brand: string; alt?: string; className?: string }) {
  const [broken, setBroken] = useState(false);
  if (!src || broken) {
    const ini = (brand || "?")
      .split(/\s+/)
      .map((w) => w[0])
      .join("")
      .slice(0, 2)
      .toUpperCase();
    return (
      <span className={`ph ${className ?? ""}`} role={alt ? "img" : undefined} aria-label={alt || undefined} aria-hidden={alt ? undefined : true}>
        {ini}
      </span>
    );
  }
  return <img className={className} src={src} alt={alt} loading="lazy" decoding="async" onError={() => setBroken(true)} />;
}
