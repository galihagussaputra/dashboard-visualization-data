import { useEffect, useState } from "react";

export const NAV_ITEMS = [
  { path: "/overview", label: "Executive Overview", eyebrow: "Portfolio view" },
  { path: "/explorer", label: "Company Explorer", eyebrow: "Company record" },
  { path: "/performance", label: "Financial Performance", eyebrow: "Reported results" },
  { path: "/ratios", label: "Financial Ratios", eyebrow: "Defined calculations" },
  { path: "/comparison", label: "Company Comparison", eyebrow: "Up to five issuers" },
  { path: "/sector", label: "Sector Analysis", eyebrow: "Peer context" },
  { path: "/data", label: "Data Management", eyebrow: "Sources and jobs" },
  { path: "/validation", label: "Data Validation", eyebrow: "Rules and review" },
  { path: "/audit", label: "Source & Audit Trail", eyebrow: "Provenance" },
  { path: "/legacy", label: "Legacy Demo", eyebrow: "Synthetic data" },
];

function normalize(hash) {
  const value = hash.replace(/^#/, "");
  if (!value) return "/overview";
  return value.startsWith("/") ? value : `/${value}`;
}

export function useHashRoute() {
  const [path, setPath] = useState(() => normalize(window.location.hash));

  useEffect(() => {
    const handler = () => setPath(normalize(window.location.hash));
    window.addEventListener("hashchange", handler);
    if (!window.location.hash) window.location.hash = "/overview";
    return () => window.removeEventListener("hashchange", handler);
  }, []);

  return path;
}
