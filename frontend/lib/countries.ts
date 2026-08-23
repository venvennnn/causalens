export const COUNTRY_META: Record<string, { flag: string; color: string }> = {
  Singapore: { flag: "🇸🇬", color: "#d4af67" },
  Malaysia: { flag: "🇲🇾", color: "#4aa37a" },
  Vietnam: { flag: "🇻🇳", color: "#d46a54" },
  Indonesia: { flag: "🇮🇩", color: "#6ea8d4" },
  Thailand: { flag: "🇹🇭", color: "#b07ad4" },
  Philippines: { flag: "🇵🇭", color: "#4aa3c8" },
  China: { flag: "🇨🇳", color: "#c45c5c" },
  "United States": { flag: "🇺🇸", color: "#6b8cbe" },
  ASEAN: { flag: "🌏", color: "#8aa0b8" },
};

export function countryMeta(name?: string) {
  if (!name) return { flag: "•", color: "#8aa0b8" };
  return COUNTRY_META[name] || { flag: "•", color: "#8aa0b8" };
}

export function primaryCountry(countries: string[]): string {
  return countries[0] || "Regional";
}
