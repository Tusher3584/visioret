/**
 * GitHub-style identicon, generated locally.
 *
 * Deliberately not Gravatar: that would send a hash of every user's email
 * address to a third party on each page load, which is not a reasonable thing
 * for a medical research tool to do just to draw an avatar. This is a pure
 * function of the identity string -- same user, same picture, no network.
 *
 * Layout is the classic 5x5 grid mirrored about the centre column, so only 15
 * cells are decided by the hash and the result is always symmetric.
 */

/** FNV-1a. Small, fast, and well-spread for short strings like emails. */
function hashString(value: string): number {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i++) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export interface Identicon {
  /** 5x5 booleans, row-major. */
  cells: boolean[][];
  /** Foreground colour for filled cells. */
  color: string;
  /** Tinted background behind the grid. */
  background: string;
}

export function buildIdenticon(seed: string): Identicon {
  const hash = hashString(seed || "anonymous");

  // Hue from the top bits so it varies widely between adjacent seeds.
  const hue = hash % 360;
  // Fixed saturation/lightness so every generated colour stays legible on both
  // the light and dark panel surfaces rather than occasionally washing out.
  const color = `hsl(${hue} 58% 48%)`;
  const background = `hsl(${hue} 42% 92%)`;

  const cells: boolean[][] = [];
  let bits = hash;
  for (let row = 0; row < 5; row++) {
    const line: boolean[] = new Array(5).fill(false);
    for (let col = 0; col < 3; col++) {
      // Re-mix as we go so we don't run out of entropy in 32 bits.
      bits = Math.imul(bits ^ (row * 31 + col), 16777619) >>> 0;
      const on = (bits & 0x80) !== 0;
      line[col] = on;
      line[4 - col] = on; // mirror
    }
    cells.push(line);
  }

  return { cells, color, background };
}
