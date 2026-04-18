import { getLocalizedText } from "../config/appContent";
import { getImageUrl } from "../services/api";
import Card from "./Card";

function getEvidenceItems(data) {
  return [
    {
      key: "before",
      eyebrow: "Before",
      label: "Baseline image",
      description: "Historical satellite frame used as the baseline reference.",
      src: data?.before_image ? getImageUrl(data.before_image) : null,
    },
    {
      key: "after",
      eyebrow: "After",
      label: "Latest image",
      description: "Current observation image used for live parcel comparison.",
      src: data?.after_image ? getImageUrl(data.after_image) : null,
    },
    {
      key: "output",
      eyebrow: "Output",
      label: "Detection overlay",
      description: "Processed evidence view highlighting suspected encroachment.",
      src: data?.output_image ? getImageUrl(data.output_image) : null,
    },
  ];
}

export default function ImagePanel({ auth, data }) {
  const evidenceItems = getEvidenceItems(data);

  return (
    <Card
      eyebrow={getLocalizedText(auth.language, "Satellite Evidence", "Satellite Evidence")}
      title={getLocalizedText(
        auth.language,
        "Before / after / output comparison",
        "Before / after / output comparison"
      )}
    >
      <div className="evidence-comparison-header">
        <p className="body-copy">
          Review the baseline image, the latest observation, and the processed detection output in one aligned horizontal comparison.
        </p>
      </div>

      <div className="evidence-comparison-grid">
        {evidenceItems.map((item) => (
          <article className="evidence-panel" key={item.key}>
            <div className="evidence-panel-top">
              <span className="evidence-panel-eyebrow">{item.eyebrow}</span>
              <strong className="evidence-panel-title">{item.label}</strong>
            </div>

            {item.src ? (
              <div className="evidence-image-frame">
                <img alt={item.label} className="evidence-panel-image" src={item.src} />
              </div>
            ) : (
              <div className="image-empty evidence-image-frame">
                {getLocalizedText(auth.language, "Image not available", "Image not available")}
              </div>
            )}

            <p className="evidence-panel-copy">{item.description}</p>
          </article>
        ))}
      </div>
    </Card>
  );
}
