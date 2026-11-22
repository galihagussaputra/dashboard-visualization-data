import { useEffect, useMemo, useState } from "react";

import { useFilters } from "../../app/filterContext";
import { getDocuments, getPeriods, getStatement } from "../../lib/financialApi";

const STATEMENT_TABS = [
  { id: "balance_sheet", label: "Balance Sheet" },
  { id: "income_statement", label: "Income Statement" },
  { id: "cash_flow", label: "Cash Flow" },
];

function fiscalYear(period) {
  const value = Number.parseInt(period.replace(/\D/g, ""), 10);
  return Number.isFinite(value) ? value : undefined;
}

export default function StatementPage() {
  const { ticker, period, basis } = useFilters();
  const [statement, setStatement] = useState("balance_sheet");
  const [periods, setPeriods] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [statementResult, setStatementResult] = useState(null);
  const [requestError, setRequestError] = useState(null);
  const [selectedConcept, setSelectedConcept] = useState(null);
  const [visibility, setVisibility] = useState("draft");

  const request = useMemo(
    () => ({
      ticker,
      period,
      statement,
      basis,
      visibility,
      key: `${ticker}|${period}|${statement}|${basis}|${visibility}`,
    }),
    [ticker, period, statement, basis, visibility],
  );

  useEffect(() => {
    let active = true;
    getPeriods(ticker)
      .then((rows) => {
        if (active) setPeriods(rows);
      })
      .catch(() => {
        if (active) setPeriods([]);
      });
    return () => {
      active = false;
    };
  }, [ticker]);

  const sourcePeriodCode = periods.find((row) => row.label === period)?.sourcePeriodCode ?? null;

  useEffect(() => {
    if (!sourcePeriodCode) return undefined;
    let active = true;
    getDocuments({ ticker, year: fiscalYear(period), period: sourcePeriodCode })
      .then((rows) => {
        if (active) setDocuments(rows);
      })
      .catch(() => {
        if (active) setDocuments([]);
      });
    return () => {
      active = false;
    };
  }, [ticker, period, sourcePeriodCode]);

  useEffect(() => {
    let active = true;
    getStatement(request)
      .then((payload) => {
        if (!active) return;
        setRequestError(null);
        setStatementResult({ key: request.key, payload });
      })
      .catch((cause) => {
        if (!active) return;
        setRequestError({
          key: request.key,
          message: cause instanceof Error ? cause.message : "Unable to load statement",
        });
      });
    return () => {
      active = false;
    };
  }, [request]);

  const statementPayload = statementResult?.key === request.key ? statementResult.payload : null;
  const visibleError = requestError?.key === request.key ? requestError.message : "";
  const loading = !visibleError && !statementPayload;
  const selectedFact =
    statementPayload?.facts?.find((fact) => fact.concept === selectedConcept)
    ?? statementPayload?.facts?.[0]
    ?? null;

  return (
    <div className="ifi-statement-layout">
      <section className="ifi-panel" aria-label="Financial statement">
        <div className="ifi-statement-head">
          <div>
            <p className="ifi-eyebrow">Source-backed view</p>
            <h3 className="ifi-section-title">
              {statementPayload?.companyName ?? ticker} · {period} · {basis}
            </h3>
          </div>
          <div className="ifi-statement-controls">
            <div className="ifi-tabs" role="group" aria-label="Statement type">
              {STATEMENT_TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  className="ifi-tab"
                  data-active={statement === tab.id}
                  aria-pressed={statement === tab.id}
                  onClick={() => setStatement(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <label className="ifi-filter-label" htmlFor="visibility-filter">View</label>
            <select
              id="visibility-filter"
              className="ifi-select"
              value={visibility}
              onChange={(event) => setVisibility(event.target.value)}
            >
              <option value="draft">Draft</option>
              <option value="published">Published</option>
            </select>
          </div>
        </div>

        {loading && <p className="ifi-empty">Loading statement from ingested documents…</p>}
        {!loading && visibleError && <p className="ifi-error">{visibleError}</p>}
        {!loading && !visibleError && statementPayload?.facts?.length === 0 && (
          <p className="ifi-empty">No current facts are available for this statement and basis.</p>
        )}

        {!loading && !visibleError && statementPayload?.facts?.length > 0 && (
          <table className="ifi-table">
            <thead>
              <tr>
                <th>Account</th>
                <th>Concept</th>
                <th>Context</th>
                <th className="ifi-number">Value</th>
                <th>Unit</th>
                <th>Standard account</th>
                <th>Doc v.</th>
                <th>Publication</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {statementPayload.facts.map((fact) => (
                <tr
                  key={fact.concept}
                  data-selected={selectedFact?.concept === fact.concept}
                  onClick={() => setSelectedConcept(fact.concept)}
                >
                  <td>{fact.labelEn ?? fact.labelId ?? fact.concept}</td>
                  <td className="ifi-code">{fact.concept}</td>
                  <td className="ifi-code">{fact.sourceContextRef}</td>
                  <td className="ifi-number">{fact.valueDisplay}</td>
                  <td>{fact.unit}</td>
                  <td className="ifi-code">{fact.standardAccount ?? "—"}</td>
                  <td>{fact.documentVersion}</td>
                  <td><span className="ifi-status">{fact.publicationStatus}</span></td>
                  <td><span className="ifi-status">{fact.validationStatus}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <aside className="ifi-evidence" aria-label="Evidence rail">
        <p className="ifi-eyebrow">Evidence rail</p>
        <h3 className="ifi-section-title">Selected fact</h3>
        {selectedFact ? (
          <dl className="ifi-evidence-list">
            <dt>Account</dt>
            <dd>{selectedFact.labelEn ?? selectedFact.labelId}</dd>
            <dt>Concept</dt>
            <dd className="ifi-code">{selectedFact.concept}</dd>
            <dt>Value</dt>
            <dd className="ifi-number">{selectedFact.valueDisplay} {selectedFact.unit}</dd>
            <dt>Source fact</dt>
            <dd className="ifi-code">{selectedFact.sourceFactId}</dd>
            <dt>Context</dt>
            <dd className="ifi-code">{selectedFact.sourceContextRef}</dd>
            <dt>Period kind</dt>
            <dd>{selectedFact.periodKind} / {selectedFact.durationKind}</dd>
            <dt>Standard account</dt>
            <dd className="ifi-code">{selectedFact.standardAccount ?? "—"}</dd>
            <dt>Mapping</dt>
            <dd>{selectedFact.mappingStatus ?? "—"}</dd>
            <dt>Document version</dt>
            <dd>{selectedFact.documentVersion}</dd>
            <dt>Publication</dt>
            <dd><span className="ifi-status">{selectedFact.publicationStatus}</span></dd>
            <dt>Validation</dt>
            <dd><span className="ifi-status">{selectedFact.validationStatus}</span></dd>
          </dl>
        ) : (
          <p className="ifi-muted">Select a row to inspect its source reference.</p>
        )}

        <h3 className="ifi-section-title">Source documents</h3>
        <ul className="ifi-documents">
          {documents.map((document) => (
            <li key={document.id}>
              <strong>{document.fileRole}</strong>
              <span className="ifi-code">{document.fileName}</span>
              <span>{document.parseStatus}</span>
              <a href={document.sourceUrl} target="_blank" rel="noreferrer">source</a>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
