// Resolve and apply the theme before first paint, otherwise the page renders
// in the default palette for a frame and visibly snaps to the stored one.
//
// This lives in public/ as a separate file rather than inline in index.html,
// and that is a Content-Security-Policy decision, not a style preference. The
// CSP sets `script-src 'self'`, which blocks inline scripts outright -- the
// only ways to keep this inline would be `'unsafe-inline'` (which discards
// most of the protection CSP provides) or a sha256 hash pinned in nginx.conf
// (which breaks silently the moment anyone edits these lines and forgets to
// regenerate it). An external same-origin file needs neither.
//
// It must stay a plain synchronous <script src> in <head>, with no `defer`
// or `type="module"` -- both would delay execution until after first paint,
// which is exactly the flash this exists to prevent. Vite copies public/
// verbatim to the site root, so /theme-init.js resolves in dev and in build.
(function () {
  try {
    var stored = localStorage.getItem("visioret_theme");
    var theme =
      stored === "light" || stored === "dark"
        ? stored
        : window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light";
    document.documentElement.setAttribute("data-theme", theme);
  } catch (e) {
    // Private mode / storage disabled -- fall back to the OS preference.
    document.documentElement.setAttribute("data-theme", "light");
  }
})();
