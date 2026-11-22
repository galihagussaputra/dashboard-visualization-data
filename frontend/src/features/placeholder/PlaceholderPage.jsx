export default function PlaceholderPage({ title, description }) {
  return (
    <section className="ifi-panel" aria-label={title}>
      <div className="ifi-empty">
        <strong>{title} is ready for data</strong>
        <p>{description}</p>
      </div>
    </section>
  );
}
