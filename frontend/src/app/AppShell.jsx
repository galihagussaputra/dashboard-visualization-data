import { useEffect, useState } from "react";

import { useFilters } from "./filterContext";
import { NAV_ITEMS } from "./router";
import { getCompanies, getPeriods } from "../lib/financialApi";

export default function AppShell({ path, title, eyebrow, children }) {
  const { ticker, period, basis, setTicker, setPeriod, setBasis } = useFilters();
  const [companies, setCompanies] = useState([]);
  const [periods, setPeriods] = useState([]);

  useEffect(() => {
    let active = true;
    getCompanies()
      .then((rows) => {
        if (active) setCompanies(rows);
      })
      .catch(() => {
        if (active) setCompanies([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    getPeriods(ticker)
      .then((rows) => {
        if (!active) return;
        setPeriods(rows);
        setPeriod((current) => {
          if (rows.some((row) => row.label === current)) return current;
          return rows[0]?.label ?? current;
        });
      })
      .catch(() => {
        if (active) setPeriods([]);
      });
    return () => {
      active = false;
    };
  }, [ticker, setPeriod]);

  return (
    <div className="ifi-shell">
      <aside className="ifi-sidebar">
        <h1 className="ifi-brand">
          IDX Financial Intelligence
          <small>Corporate financial analytics</small>
        </h1>
        <ul className="ifi-nav">
          {NAV_ITEMS.map((item) => (
            <li key={item.path}>
              <a href={`#${item.path}`} data-active={path === item.path}>
                {item.label}
              </a>
            </li>
          ))}
        </ul>
      </aside>
      <div className="ifi-main">
        <header className="ifi-topbar">
          <div className="ifi-filter-group">
            <label className="ifi-filter-label" htmlFor="ticker-filter">Issuer</label>
            <select
              id="ticker-filter"
              className="ifi-select"
              value={ticker}
              onChange={(event) => setTicker(event.target.value)}
            >
              {companies.length === 0 && <option value={ticker}>{ticker}</option>}
              {companies.map((company) => (
                <option key={company.ticker} value={company.ticker}>
                  {company.ticker}
                </option>
              ))}
            </select>
          </div>
          <div className="ifi-filter-group">
            <label className="ifi-filter-label" htmlFor="period-filter">Period</label>
            <select
              id="period-filter"
              className="ifi-select"
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
            >
              {periods.length === 0 && <option value={period}>{period}</option>}
              {periods.map((row) => (
                <option key={row.id} value={row.label}>
                  {row.label}
                </option>
              ))}
            </select>
          </div>
          <div className="ifi-filter-group">
            <label className="ifi-filter-label" htmlFor="basis-filter">Reporting basis</label>
            <select
              id="basis-filter"
              className="ifi-select"
              value={basis}
              onChange={(event) => setBasis(event.target.value)}
            >
              <option value="consolidated">Consolidated</option>
              <option value="separate">Separate</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>
          <span className="ifi-draft-flag">Draft · internal review only</span>
        </header>
        <main className="ifi-content">
          <div className="ifi-page-head">
            <p className="ifi-eyebrow">{eyebrow}</p>
            <h2 className="ifi-title">{title}</h2>
            <p className="ifi-meta">
              Statement values are ingested from IDX source documents and shown with concept and context references.
            </p>
          </div>
          {children}
          <p className="ifi-footnote">
            Reporting basis, period, currency and unit are shown with every value. Missing values are shown as —.
          </p>
        </main>
      </div>
    </div>
  );
}
