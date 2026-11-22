import { useCallback, useEffect, useMemo, useState } from "react";

import { useFilters } from "../../app/filterContext";
import { currentUser, login, logout } from "../../lib/authApi";
import {
  listAuditEvents,
  listMappings,
  listMetrics,
  listPublicationEvents,
  listRestatements,
  listValidationLogs,
  publishScope,
  recalculateMetrics,
  runValidation,
} from "../../lib/trustApi";

export default function TrustPage({ audit = false }) {
  const { ticker, period, basis } = useFilters();
  const [user, setUser] = useState(null);
  const [email, setEmail] = useState("admin@localhost.invalid");
  const [password, setPassword] = useState("");
  const [validation, setValidation] = useState(null);
  const [metrics, setMetrics] = useState([]);
  const [mappings, setMappings] = useState([]);
  const [events, setEvents] = useState([]);
  const [logs, setLogs] = useState([]);
  const [auditEvents, setAuditEvents] = useState([]);
  const [restatements, setRestatements] = useState([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const scope = useMemo(() => ({ ticker, period, basis }), [ticker, period, basis]);
  const roles = user?.roles ?? [];
  const canReview = roles.includes("reviewer") || roles.includes("admin");
  const canPublish = roles.includes("publisher") || roles.includes("admin");

  const refresh = useCallback(async () => {
    const [metricsResult, mappingsResult, eventsResult, logsResult, auditResult, restatementsResult] =
      await Promise.allSettled([
        listMetrics(scope),
        listMappings(),
        listPublicationEvents(),
        listValidationLogs(),
        listAuditEvents(),
        listRestatements({ ticker, period }),
      ]);
    if (metricsResult.status === "fulfilled") setMetrics(metricsResult.value);
    if (mappingsResult.status === "fulfilled") setMappings(mappingsResult.value);
    if (eventsResult.status === "fulfilled") setEvents(eventsResult.value);
    if (logsResult.status === "fulfilled") setLogs(logsResult.value);
    if (auditResult.status === "fulfilled") setAuditEvents(auditResult.value);
    if (restatementsResult.status === "fulfilled") setRestatements(restatementsResult.value);
  }, [scope, ticker, period]);

  useEffect(() => {
    let active = true;
    currentUser().then((value) => {
      if (active) setUser(value);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    refresh().catch(() => setMessage("Trust data could not be loaded."));
  }, [refresh]);

  async function handleLogin(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      setUser(await login({ email, password }));
      setMessage("Signed in.");
      await refresh();
    } catch (cause) {
      setMessage(cause.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleLogout() {
    await logout();
    setUser(null);
    setMessage("Signed out.");
  }

  async function handleValidation() {
    setBusy(true);
    setMessage("");
    try {
      const result = await runValidation(scope);
      setValidation(result);
      setMessage(`Validation ${result.run.status}: ${result.run.summary.issue_count ?? 0} findings.`);
      await refresh();
    } catch (cause) {
      setMessage(cause.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleRecalculate() {
    setBusy(true);
    setMessage("");
    try {
      const result = await recalculateMetrics(scope);
      setMessage(`Recalculated ${result.metrics.length} metrics.`);
      await refresh();
    } catch (cause) {
      setMessage(cause.message);
    } finally {
      setBusy(false);
    }
  }

  async function handlePublish() {
    setBusy(true);
    setMessage("");
    try {
      const result = await publishScope(scope);
      setMessage(`Published event ${result.id}: ${result.facts_published} facts, ${result.metrics_published} metrics.`);
      await refresh();
    } catch (cause) {
      setMessage(cause.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ifi-trust-layout">
      <section className="ifi-panel">
        <p className="ifi-eyebrow">Server-side trust</p>
        <h3 className="ifi-section-title">{audit ? "Source and audit trail" : "Validation and publication"}</h3>
        {user ? (
          <div className="ifi-trust-session">
            <span>{user.displayName}</span>
            <span className="ifi-code">{roles.join(", ")}</span>
            <button type="button" className="ifi-tab" onClick={handleLogout}>Sign out</button>
          </div>
        ) : (
          <form className="ifi-trust-login" onSubmit={handleLogin}>
            <label className="ifi-filter-label" htmlFor="trust-email">Email</label>
            <input
              id="trust-email"
              className="ifi-select"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <label className="ifi-filter-label" htmlFor="trust-password">Password</label>
            <input
              id="trust-password"
              className="ifi-select"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <button type="submit" className="ifi-tab" disabled={busy}>Sign in</button>
          </form>
        )}

        {message && <p className="ifi-trust-message">{message}</p>}

        {!audit && (
          <div className="ifi-trust-actions">
            <button type="button" className="ifi-tab" disabled={busy || !user} onClick={handleValidation}>
              Run validation
            </button>
            <button type="button" className="ifi-tab" disabled={busy || !user} onClick={handleRecalculate}>
              Recalculate metrics
            </button>
            <button type="button" className="ifi-tab" disabled={busy || !canPublish} onClick={handlePublish}>
              Publish scope
            </button>
            {!canPublish && <span className="ifi-muted">Publisher role required to publish.</span>}
            {canReview && <span className="ifi-muted">Reviewer role available.</span>}
          </div>
        )}
      </section>

      {!audit && (
        <>
          <section className="ifi-panel">
            <h3 className="ifi-section-title">Validation findings</h3>
            {validation ? (
              <p className="ifi-muted">
                {validation.run.status} · {validation.failures.length} blockers · {validation.warnings.length} warnings
              </p>
            ) : (
              <p className="ifi-muted">Run validation to evaluate this scope.</p>
            )}
            <ul className="ifi-documents">
              {logs.slice(0, 12).map((log) => (
                <li key={log.id}>
                  <strong>{log.rule_code} · {log.severity_level}</strong>
                  <span>{log.message}</span>
                  <span className="ifi-code">{log.rule_category} / {log.status}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="ifi-panel">
            <h3 className="ifi-section-title">Versioned metrics</h3>
            <table className="ifi-table">
              <thead>
                <tr><th>Metric</th><th>Value</th><th>Status</th><th>Formula</th></tr>
              </thead>
              <tbody>
                {metrics.map((metric) => (
                  <tr key={metric.id}>
                    <td>{metric.name}</td>
                    <td className="ifi-number">{metric.value ?? "—"}</td>
                    <td>{metric.calculation_status}</td>
                    <td className="ifi-code">{metric.formula_version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="ifi-panel">
            <h3 className="ifi-section-title">Account mappings</h3>
            <ul className="ifi-documents">
              {mappings.slice(0, 12).map((mapping) => (
                <li key={mapping.id}>
                  <strong>{mapping.source_account_name}</strong>
                  <span className="ifi-code">{mapping.standard_account_code ?? "unmapped"}</span>
                  <span>{mapping.status}</span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}

      {audit && (
        <>
          <section className="ifi-panel">
            <h3 className="ifi-section-title">Publication history</h3>
            <ul className="ifi-documents">
              {events.map((event) => (
                <li key={event.id}>
                  <strong>Event {event.id} · {event.status}</strong>
                  <span className="ifi-code">{event.reporting_basis}</span>
                  <span>{JSON.stringify(event.publication_metadata)}</span>
                </li>
              ))}
            </ul>
          </section>
          <section className="ifi-panel">
            <h3 className="ifi-section-title">Restatements</h3>
            <ul className="ifi-documents">
              {restatements.map((item) => (
                <li key={item.id}>
                  <strong>{item.concept} · v{item.document_version}</strong>
                  <span>{item.reason}</span>
                  <span>{item.approval_status}</span>
                </li>
              ))}
            </ul>
          </section>
          <section className="ifi-panel">
            <h3 className="ifi-section-title">Audit events</h3>
            <ul className="ifi-documents">
              {auditEvents.length === 0 && <li className="ifi-muted">Sign in with a reviewer role to view audit events.</li>}
              {auditEvents.map((event) => (
                <li key={event.id}>
                  <strong>{event.action}</strong>
                  <span>{event.entity_type} / {event.entity_id}</span>
                  <span className="ifi-code">{event.created_at}</span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
