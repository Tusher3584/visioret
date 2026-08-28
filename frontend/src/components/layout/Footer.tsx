/**
 * Site footer: attribution line at the bottom of every page.
 *
 * Uses a real <footer> element so it lands in the accessibility tree as a
 * contentinfo landmark, alongside the existing header/nav/main.
 *
 * The year is computed rather than hardcoded, so the notice does not quietly
 * go stale on 1 January. `getFullYear()` reads the viewer's local clock,
 * which is the right source for a copyright line.
 *
 * Colour is `text-muted`, not `text-subtle`. At 11px on the canvas background
 * `text-subtle` measures 4.07:1 in the light theme -- under the 4.5:1 that
 * WCAG AA requires for text this size. `text-muted` clears it in both themes.
 */
export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="mt-10 border-t border-line">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-1 px-4 py-6 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p className="text-[11px] text-muted">
          © {year} Rifat Ahmed Tushar · Visioret. All rights reserved.
        </p>
        <p className="text-[11px] text-muted">
          Research and demonstration system — not a medical device.
        </p>
      </div>
    </footer>
  );
}
