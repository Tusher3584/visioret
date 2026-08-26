import { buildIdenticon } from "../../lib/identicon";

interface AvatarProps {
  /** Stable identity string -- email, so the picture never changes for a user. */
  seed: string;
  size?: number;
  className?: string;
}

/** Renders the generated identicon as an inline SVG, clipped to a circle. */
export function Avatar({ seed, size = 28, className = "" }: AvatarProps) {
  const { cells, color, background } = buildIdenticon(seed);
  const cell = 100 / 5;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      className={`shrink-0 rounded-full ${className}`}
      role="img"
      aria-label="Profile picture"
    >
      <rect width="100" height="100" fill={background} />
      {cells.map((row, y) =>
        row.map((on, x) =>
          on ? (
            <rect
              key={`${x}-${y}`}
              x={x * cell}
              y={y * cell}
              width={cell}
              height={cell}
              fill={color}
            />
          ) : null,
        ),
      )}
    </svg>
  );
}
