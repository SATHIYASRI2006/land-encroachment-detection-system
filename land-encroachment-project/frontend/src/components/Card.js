export default function Card({
  action,
  children,
  className = "",
  eyebrow,
  title,
}) {
  return (
    <section className={`ui-card ${className}`.trim()}>
      {(eyebrow || title || action) && (
        <div className="ui-card-header">
          <div>
            {eyebrow ? <p className="section-eyebrow">{eyebrow}</p> : null}
            {title ? <h3 className="ui-card-title">{title}</h3> : null}
          </div>
          {action ? <div>{action}</div> : null}
        </div>
      )}
      {children}
    </section>
  );
}
