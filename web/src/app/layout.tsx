import type { Metadata, Viewport } from "next";
import { EB_Garamond, Montserrat } from "next/font/google";
import { BRAND } from "@/lib/brand";
import "./globals.css";

// The practice website's own typefaces.
const montserrat = Montserrat({
  variable: "--font-montserrat",
  subsets: ["latin"],
});

const garamond = EB_Garamond({
  variable: "--font-garamond",
  subsets: ["latin"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: `${BRAND.fullName} | Patient Assistant`,
  description: `Ask ${BRAND.name} about visiting the practice in ${BRAND.city} and everyday dental care, with answers you can check.`,
};

export const viewport: Viewport = {
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8f6f1" },
    { media: "(prefers-color-scheme: dark)", color: "#0d0d0d" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${montserrat.variable} ${garamond.variable} h-full antialiased`}>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
