import AppShell from "./app/AppShell";
import FilterProvider from "./app/FilterProvider";
import { NAV_ITEMS, useHashRoute } from "./app/router";
import Dashboard from "./components/Dashboard";
import PlaceholderPage from "./features/placeholder/PlaceholderPage";
import StatementPage from "./features/statements/StatementPage";
import TrustPage from "./features/trust/TrustPage";

const DESCRIPTIONS = {
  "/overview": "Company totals, rankings and sector distribution will appear here after publication.",
  "/explorer": "Issuer master data, reporting periods and document status will appear here.",
  "/performance": "Income statement, balance sheet and cash-flow trends will appear here.",
  "/ratios": "Versioned ratio definitions and calculated values will appear here.",
  "/comparison": "Up to five issuers can be compared with compatible periods and reporting bases.",
  "/sector": "Sector aggregates will distinguish sums, means and medians.",
  "/data": "Document discovery, upload, extraction previews and job history will appear here.",
  "/validation": "Validation rule results and review actions will appear here.",
  "/audit": "Source documents, extraction context and publication history will appear here.",
};

export default function App() {
  return (
    <FilterProvider>
      <AppRoutes />
    </FilterProvider>
  );
}

function AppRoutes() {
  const path = useHashRoute();

  if (path === "/legacy") {
    return <Dashboard />;
  }

  const item = NAV_ITEMS.find((entry) => entry.path === path) || NAV_ITEMS[0];

  return (
    <AppShell path={item.path} title={item.label} eyebrow={item.eyebrow}>
      {path === "/performance" ? (
        <StatementPage />
      ) : path === "/validation" || path === "/audit" ? (
        <TrustPage audit={path === "/audit"} />
      ) : (
        <PlaceholderPage title={item.label} description={DESCRIPTIONS[item.path]} />
      )}
    </AppShell>
  );
}
