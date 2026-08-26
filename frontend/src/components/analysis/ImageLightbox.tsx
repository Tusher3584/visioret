import { useEffect, useRef } from "react";
import { mediaUrl } from "../../api/client";

interface LightboxImage {
  url: string;
  label: string;
  alt: string;
}

interface ImageLightboxProps {
  images: LightboxImage[];
  activeIndex: number;
  onChangeIndex: (index: number) => void;
  onClose: () => void;
}

/**
 * Full-screen inspection view. Purely a frontend affordance -- it enlarges the
 * already-rendered images; it does not (and cannot) alter the Grad-CAM
 * overlay, which the backend bakes into a single image.
 *
 * Keyboard: Escape closes, Left/Right switch between the images. Focus is
 * moved into the dialog on open and restored to the trigger on close.
 */
export function ImageLightbox({ images, activeIndex, onChangeIndex, onClose }: ImageLightboxProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<Element | null>(null);
  const active = images[activeIndex];

  useEffect(() => {
    previouslyFocused.current = document.activeElement;
    dialogRef.current?.focus();
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      (previouslyFocused.current as HTMLElement | null)?.focus?.();
    };
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key === "ArrowRight") {
        onChangeIndex((activeIndex + 1) % images.length);
        return;
      }
      if (event.key === "ArrowLeft") {
        onChangeIndex((activeIndex - 1 + images.length) % images.length);
        return;
      }
      // Trap Tab inside the dialog -- without this, tabbing walks out into the
      // page behind the overlay, which is unreachable and invisible.
      if (event.key === "Tab") {
        const focusables = dialogRef.current?.querySelectorAll<HTMLElement>("button");
        if (!focusables || focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        const current = document.activeElement;
        if (event.shiftKey && (current === first || current === dialogRef.current)) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && current === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [activeIndex, images.length, onChangeIndex, onClose]);

  if (!active) return null;

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label={`${active.label}, full screen`}
      tabIndex={-1}
      className="fixed inset-0 z-50 flex flex-col bg-imaging/97"
    >
      <div className="flex items-center justify-between border-b border-imaging-line px-4 py-2.5">
        <div
          role="tablist"
          aria-label="Choose image"
          className="flex items-center gap-1"
        >
          {images.map((image, index) => (
            <button
              key={image.label}
              role="tab"
              aria-selected={index === activeIndex}
              onClick={() => onChangeIndex(index)}
              className={`rounded-[3px] px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.1em] transition-colors ${
                index === activeIndex
                  ? "bg-slate-100 text-slate-900"
                  : "text-slate-400 hover:text-slate-100"
              }`}
            >
              {image.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-[3px] border border-slate-600 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.1em] text-slate-300 transition-colors hover:border-slate-300 hover:text-white"
        >
          Close
        </button>
      </div>

      <div className="relative flex min-h-0 flex-1 items-center justify-center p-4">
        <div className="vr-grid absolute inset-0" aria-hidden="true" />
        <img
          src={mediaUrl(active.url)}
          alt={active.alt}
          className="relative max-h-full max-w-full object-contain"
        />
      </div>

      <p className="border-t border-imaging-line px-4 py-2 text-center text-[11px] text-slate-500">
        Esc to close · ← → to switch image
      </p>
    </div>
  );
}
