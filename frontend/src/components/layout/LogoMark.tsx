/**
 * Reticle-and-contour mark: four corner ticks (the framing marks used on
 * medical image viewports), a curved retinal contour, and a focal point.
 * Deliberately not an app-store style rounded tile -- it should read as an
 * instrument marking.
 */
export function LogoMark({ size = 26 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="shrink-0"
    >
      <g stroke="currentColor" strokeWidth="1.6" strokeLinecap="square" className="text-accent">
        <path d="M1.5 7V1.5H7" />
        <path d="M21 1.5h5.5V7" />
        <path d="M26.5 21v5.5H21" />
        <path d="M7 26.5H1.5V21" />
      </g>
      <path
        d="M4 17.5c3.4 0 4.6-6 10-6s6.6 6 10 6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        className="text-ink"
        fill="none"
      />
      <circle cx="14" cy="11.9" r="2.1" className="fill-accent" />
    </svg>
  );
}
