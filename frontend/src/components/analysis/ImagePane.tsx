import { mediaUrl } from "../../api/client";

interface ImagePaneProps {
  url: string;
  label: string;
  alt: string;
  /** Optional caption line under the label badge. */
  note?: string;
  onExpand?: () => void;
  /** Tailwind aspect / height classes for the image box. */
  frameClassName?: string;
}

/**
 * One labelled image on the dark imaging surface.
 *
 * object-contain is mandatory here: OCT B-scans arrive at aspect ratios from
 * roughly 1:1 to 2.7:1 depending on the source scanner, and cropping could
 * remove diagnostically meaningful tissue.
 */
export function ImagePane({
  url,
  label,
  alt,
  note,
  onExpand,
  frameClassName = "aspect-[3/2]",
}: ImagePaneProps) {
  return (
    <figure className="group relative flex min-w-0 flex-col border border-imaging-line bg-imaging">
      <div className={`relative w-full overflow-hidden ${frameClassName}`}>
        <div className="vr-grid absolute inset-0" aria-hidden="true" />
        <img src={mediaUrl(url)} alt={alt} className="relative h-full w-full object-contain" />

        <figcaption className="pointer-events-none absolute left-0 top-0 flex flex-col gap-0.5 bg-imaging/85 px-2 py-1">
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-slate-200">
            {label}
          </span>
          {note && <span className="text-[10px] leading-tight text-slate-400">{note}</span>}
        </figcaption>

        {onExpand && (
          <button
            type="button"
            // Focus the trigger explicitly before opening: some browsers do not
            // focus a button on mouse click, which would leave the lightbox with
            // nothing to restore focus to when it closes.
            onClick={(event) => {
              event.currentTarget.focus();
              onExpand();
            }}
            className="absolute right-1.5 top-1.5 rounded-[3px] border border-slate-600/70 bg-imaging/85 px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-slate-300 opacity-0 transition-opacity hover:border-slate-400 hover:text-white focus-visible:opacity-100 group-hover:opacity-100"
            aria-label={`View ${label} full screen`}
          >
            Expand
          </button>
        )}
      </div>
    </figure>
  );
}
