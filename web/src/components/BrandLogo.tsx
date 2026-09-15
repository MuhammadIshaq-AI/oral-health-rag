"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { BRAND } from "@/lib/brand";
import { ToothMark } from "./ToothMark";

/**
 * The practice logo on a tile sized for the header. Checks the file exists before rendering it, so a
 * missing logo shows the tooth mark rather than a broken-image icon (an <img> can fail before React
 * hydrates and attaches onError).
 */
export function BrandLogo({ className = "" }: { className?: string }) {
  const [available, setAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    fetch(BRAND.logo, { method: "HEAD" })
      .then((res) => setAvailable(res.ok && (res.headers.get("content-type") ?? "").startsWith("image/")))
      .catch(() => setAvailable(false));
  }, []);

  if (available === false) return <ToothMark className={`h-10 w-10 ${className}`} />;

  return (
    <span
      className={`relative inline-flex h-10 w-20 shrink-0 items-center justify-center overflow-hidden rounded-xl px-2 shadow-card ${
        BRAND.logoOnDark ? "bg-[#0d0d0d] ring-1 ring-accent/30" : "border border-border bg-surface"
      } ${className}`}
    >
      {available && (
        <Image
          src={BRAND.logo}
          alt={`${BRAND.name} logo`}
          width={160}
          height={80}
          priority
          unoptimized
          onError={() => setAvailable(false)}
          className="h-full w-full object-contain"
        />
      )}
    </span>
  );
}
