// Original SVG artwork for Case Clock (no third-party images).
const R = "#c4232b", INK = "#1c1814", PAPER = "#f5ecdb", GOLD = "#e3a23b", DEEP = "#9c1820";

export const logo = (stroke = R) => `<svg viewBox="0 0 30 38" aria-hidden="true"><g fill="none" stroke="${stroke}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
<path d="M3 2.5h24M3 35.5h24"/><path d="M6 2.5c0 9 9 11 9 16.5S6 26.5 6 35.5M24 2.5c0 9-9 11-9 16.5s9 7.5 9 16.5"/></g>
<path d="M10 9.5h10c-1.5 3-5 4.5-5 7.5-0-3-3.5-4.5-5-7.5zM9 33c1.5-4 6-5 6-8 0 3 4.5 4 6 8z" fill="${stroke}"/></svg>`;

export const icons = {
  hourglass: logo(R),
  calendar: `<svg viewBox="0 0 48 48" fill="none" stroke="${R}" stroke-width="2.6" aria-hidden="true"><rect x="5" y="9" width="38" height="33" rx="4"/><path d="M5 18h38M15 5v8M33 5v8"/><path d="M13 26h4M22 26h4M31 26h4M13 33h4M22 33h4" stroke-linecap="round"/></svg>`,
  bars: `<svg viewBox="0 0 48 48" fill="none" stroke="${R}" stroke-width="2.6" aria-hidden="true"><rect x="6" y="26" width="8" height="16"/><rect x="20" y="16" width="8" height="26"/><rect x="34" y="6" width="8" height="36"/></svg>`,
  clock: `<svg viewBox="0 0 32 32" fill="none" stroke="${R}" stroke-width="2.4" aria-hidden="true"><circle cx="16" cy="16" r="13"/><path d="M16 8v9l6 3" stroke-linecap="round"/></svg>`,
  layers: `<svg viewBox="0 0 32 32" fill="none" stroke="${R}" stroke-width="2.4" stroke-linejoin="round" aria-hidden="true"><path d="M16 4 3 11l13 7 13-7z"/><path d="m3 16 13 7 13-7M3 21l13 7 13-7"/></svg>`,
  cal: `<svg viewBox="0 0 32 32" fill="none" stroke="${R}" stroke-width="2.4" aria-hidden="true"><rect x="3" y="6" width="26" height="23" rx="3"/><path d="M3 13h26M10 3v6M22 3v6"/></svg>`,
  doc: `<svg viewBox="0 0 24 24" fill="none" stroke="${R}" stroke-width="1.8" aria-hidden="true"><path d="M6 2h9l4 4v16H6z"/><path d="M9 11h7M9 15h7M9 19h4"/></svg>`,
  scales: `<svg viewBox="0 0 24 24" fill="none" stroke="${R}" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M12 3v18M7 21h10M4 7h16"/><path d="m4 7-3 7a3 3 0 0 0 6 0zM20 7l-3 7a3 3 0 0 0 6 0z"/></svg>`,
  building: `<svg viewBox="0 0 24 24" fill="none" stroke="${R}" stroke-width="1.8" aria-hidden="true"><path d="M2 21h20M4 18h16M12 3 3 8h18z"/><path d="M6 10v8M10 10v8M14 10v8M18 10v8"/></svg>`,
  globe: `<svg viewBox="0 0 24 24" fill="none" stroke="${R}" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/></svg>`,
  home: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 11 12 4l9 7v9h-6v-6H9v6H3z"/></svg>`,
  hg: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 3h14M5 21h14M7 3c0 6 5 6 5 9s-5 3-5 9M17 3c0 6-5 6-5 9s5 3 5 9"/></svg>`,
  calsm: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>`,
  barsm: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 20V12M12 20V6M19 20V9"/></svg>`,
};

// Hero: court dome + oversized hourglass + scales, cream line art on red.
export const hero = () => `<svg viewBox="0 0 600 440" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Illustration: an hourglass in front of a court building">
<defs>
 <pattern id="dots" width="8" height="8" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="${DEEP}" opacity=".45"/></pattern>
 <linearGradient id="sand" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${GOLD}"/><stop offset="1" stop-color="#c47f1d"/></linearGradient>
</defs>
<rect width="600" height="440" fill="${R}"/><rect width="600" height="440" fill="url(#dots)"/>
<circle cx="420" cy="150" r="120" fill="${DEEP}" opacity=".35"/>
<g fill="none" stroke="${PAPER}" stroke-width="2.4" opacity=".95">
 <path d="M330 300V200h200v100"/>
 <path d="M345 200c0-58 40-86 85-86s85 28 85 86"/>
 <path d="M372 200c0-40 26-62 58-62s58 22 58 62"/>
 <path d="M430 114V92M424 92h12M430 84v-8"/>
 <path d="M318 200h224M318 212h224"/>
 <path d="M346 212v88M372 212v88M398 212v88M462 212v88M488 212v88M514 212v88"/>
 <path d="M410 300v-46a20 20 0 0 1 40 0v46"/>
 <path d="M300 300h260M290 312h280M280 324h300"/>
 <path d="M345 170h170" stroke-dasharray="4 8"/>
</g>
<g fill="${PAPER}" opacity=".9"><path d="M330 200h200v-6H330z"/></g>
<!-- hourglass -->
<g transform="translate(110 40)">
 <rect x="0" y="0" width="200" height="22" rx="4" fill="${INK}"/>
 <rect x="0" y="338" width="200" height="22" rx="4" fill="${INK}"/>
 <path d="M18 22h164c0 92-62 110-62 158s62 66 62 158H18c0-92 62-110 62-158S18 114 18 22z" fill="${PAPER}" stroke="${INK}" stroke-width="7"/>
 <path d="M44 60h112c-8 46-50 62-56 98-6-36-48-52-56-98z" fill="url(#sand)"/>
 <path d="M100 160v118" stroke="${GOLD}" stroke-width="4" stroke-dasharray="2 6" stroke-linecap="round"/>
 <path d="M34 336c10-46 44-58 66-60 22 2 56 14 66 60z" fill="url(#sand)"/>
 <rect x="10" y="22" width="10" height="316" fill="${INK}"/><rect x="180" y="22" width="10" height="316" fill="${INK}"/>
</g>
<!-- scales -->
<g transform="translate(40 250)" stroke="${INK}" stroke-width="5" stroke-linecap="round" fill="none">
 <path d="M70 0v150M30 150h80M0 26h140"/>
 <path d="M0 26 -22 86h44zM140 26l-22 60h44z" stroke-width="3"/>
</g>
<g transform="translate(40 250)" fill="${GOLD}" stroke="${INK}" stroke-width="3">
 <path d="M-26 86h52a26 14 0 0 1-52 0z"/><path d="M114 86h52a26 14 0 0 1-52 0z"/><circle cx="70" cy="0" r="9"/>
</g>
</svg>`;

export const brush = () => `<svg class="brush" viewBox="0 0 400 16" preserveAspectRatio="none" aria-hidden="true"><path d="M4 11C90 4 210 2 396 6c-120 2-260 4-330 9" fill="none" stroke="${R}" stroke-width="5" stroke-linecap="round"/></svg>`;

export const vignetteScales = () => `<svg viewBox="0 0 100 100" aria-hidden="true"><g stroke="${INK}" stroke-width="3" fill="none" stroke-linecap="round"><path d="M50 18v66M34 84h32M18 30h64"/><path d="M18 30 8 58h20zM82 30 72 58h20z" stroke-width="2"/></g><g fill="${PAPER}" stroke="${INK}" stroke-width="2"><path d="M6 58h24a12 6 0 0 1-24 0zM70 58h24a12 6 0 0 1-24 0z"/><circle cx="50" cy="18" r="5"/></g></svg>`;
export const vignetteHourglass = () => `<svg viewBox="0 0 100 100" aria-hidden="true"><g stroke="${INK}" stroke-width="3" fill="none"><path d="M26 12h48M26 88h48M32 12c0 22 16 26 16 38S32 66 32 88M68 12c0 22-16 26-16 38s16 16 16 38"/></g><path d="M38 24h24c-3 10-11 14-12 22-1-8-9-12-12-22zM36 84c4-12 12-14 14-15 2 1 10 3 14 15z" fill="${R}"/></svg>`;
export const vignettePen = () => `<svg viewBox="0 0 100 100" aria-hidden="true"><g stroke="${INK}" stroke-width="2.5" fill="none"><path d="M14 20h46l12 12v52H14z"/><path d="M22 36h34M22 46h34M22 56h26M22 66h20"/><path d="m60 78 26-40 6 4-26 40-9 4z" fill="${PAPER}"/></g><path d="M60 78l6 4-9 4z" fill="${R}"/></svg>`;

export const courthouse = () => `<svg viewBox="0 0 320 140" aria-hidden="true"><g fill="none" stroke="${INK}" stroke-width="1.6" opacity=".85">
<path d="M10 132h300"/><path d="M60 132V78h200v54"/><path d="M80 78c0-30 36-46 80-46s80 16 80 46"/><path d="M110 78c0-20 22-32 50-32s50 12 50 32"/>
<path d="M160 32V18M156 18h8"/><path d="M50 78h220M50 86h220"/>
<path d="M76 86v46M96 86v46M116 86v46M204 86v46M224 86v46M244 86v46"/><path d="M146 132v-26a14 14 0 0 1 28 0v26"/>
<path d="M20 132v-40c0-10 10-16 14-30 4 14 14 20 14 30v40M286 132v-40c0-10 10-16 14-30 4 14 14 20 14 30v40" />
<path d="M34 62c-6-8-14-8-20-4 8 0 12 4 14 8M300 62c6-8 14-8 20-4-8 0-12 4-14 8"/></g></svg>`;
