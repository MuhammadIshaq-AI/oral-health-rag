/**
 * Practice branding. Drop the logo file at `web/public/brand/logo.png` (a wide PNG/SVG with a
 * transparent background works best). Until it exists, the UI falls back to the tooth mark.
 */
export const BRAND = {
  name: "Scope Dental Practice",
  city: "Islamabad",
  fullName: "Scope Dental Practice Islamabad",
  tagline: "Microscope-enhanced luxury boutique dentistry",
  website: "https://scopedental.pk",
  /** Shown in the contact card when set. */
  address: "",
  mapsUrl: "https://maps.app.goo.gl/wMKe9UW2HCft5WR99",
  logo: "/brand/logo.png",
  /** The practice logo is white, so it is shown on a dark tile. Set false for a dark/coloured logo. */
  logoOnDark: true,
  phones: ["+92 330 1584 888", "+92 351 2284 888"],
  whatsapp: "https://wa.me/923301584888",
  instagram: "https://www.instagram.com/scopedentalpracticeislamabad/",
};

export const telHref = (phone: string) => `tel:${phone.replace(/\s+/g, "")}`;
