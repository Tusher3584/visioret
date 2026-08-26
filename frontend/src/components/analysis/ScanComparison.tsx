import { useState } from "react";
import { ImageLightbox } from "./ImageLightbox";
import { ImagePane } from "./ImagePane";

interface ScanComparisonProps {
  originalImageUrl: string;
  gradcamOverlayUrl: string;
}

type ViewMode = "compare" | "original" | "gradcam";

const MODES: { id: ViewMode; label: string }[] = [
  { id: "compare", label: "Compare" },
  { id: "original", label: "Original" },
  { id: "gradcam", label: "Grad-CAM" },
];

/**
 * The imaging workspace -- the primary object of attention on both the
 * prediction page and the scan detail page.
 *
 * Compare mode is side-by-side on desktop and stacked on mobile (so neither
 * image is squeezed below a readable size). The single-image modes hand the
 * full width to one scan for closer reading, and Expand opens a full-screen
 * inspection view.
 */
export function ScanComparison({ originalImageUrl, gradcamOverlayUrl }: ScanComparisonProps) {
  const [mode, setMode] = useState<ViewMode>("compare");
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const images = [
    {
      url: originalImageUrl,
      label: "Original",
      alt: "The uploaded retinal OCT B-scan, unmodified",
    },
    {
      url: gradcamOverlayUrl,
      label: "Grad-CAM",
      alt: "The same OCT scan with the Grad-CAM heat overlay showing the region that drove the model's decision",
    },
  ];

  return (
    <section aria-labelledby="imaging-heading" className="flex flex-col border border-line bg-surface rounded-[3px]">
      <h2 id="imaging-heading" className="sr-only">
        Scan imaging
      </h2>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-3 py-2">
        <div role="tablist" aria-label="Image view mode" className="flex items-center gap-0.5">
          {MODES.map((m) => (
            <button
              key={m.id}
              role="tab"
              aria-selected={mode === m.id}
              onClick={() => setMode(m.id)}
              className={`rounded-[3px] px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
                mode === m.id
                  ? "bg-accent-soft text-accent"
                  : "text-muted hover:bg-raised hover:text-ink"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-subtle">
          Grad-CAM · layer4 activation
        </p>
      </div>

      <div className="p-3">
        {mode === "compare" ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <ImagePane
              {...images[0]}
              note="As uploaded"
              onExpand={() => setLightboxIndex(0)}
              frameClassName="aspect-[3/2]"
            />
            <ImagePane
              {...images[1]}
              note="Model attention"
              onExpand={() => setLightboxIndex(1)}
              frameClassName="aspect-[3/2]"
            />
          </div>
        ) : (
          <ImagePane
            {...(mode === "original" ? images[0] : images[1])}
            note={mode === "original" ? "As uploaded" : "Model attention"}
            onExpand={() => setLightboxIndex(mode === "original" ? 0 : 1)}
            frameClassName="aspect-[16/9] md:aspect-[21/9]"
          />
        )}
      </div>

      <p className="border-t border-line px-3 py-2 text-xs leading-relaxed text-muted">
        <span className="font-medium text-ink">Reading the overlay: </span>
        warmer regions mark the areas that most influenced the classification. The heatmap is
        rendered server-side onto the scan and is not adjustable here.
      </p>

      {lightboxIndex !== null && (
        <ImageLightbox
          images={images}
          activeIndex={lightboxIndex}
          onChangeIndex={setLightboxIndex}
          onClose={() => setLightboxIndex(null)}
        />
      )}
    </section>
  );
}
