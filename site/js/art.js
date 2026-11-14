// Original SVG artwork for Case Clock (no third-party images).
const R = "#c4232b", INK = "#1c1814", PAPER = "#f5ecdb", GOLD = "#e3a23b", DEEP = "#9c1820";
const SUIT = "#1d3a39", SHIRT = "#fbf6ec", SKIN = "#e3a984", SKIN_SH = "#c48461", BAND = "#eef4f6";

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
  book: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M5 17a3 3 0 0 1 3-3h11M9 8h6"/></svg>`,
  helpsm: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17.5v.01"/></svg>`,
  barsm: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 20V12M12 20V6M19 20V9"/></svg>`,
};

// Hero: original blindfolded Justice figure with scales in front of a court dome, on red.
export const hero = () => `<svg viewBox="0 0 600 440" preserveAspectRatio="xMidYMin slice" role="img" aria-label="Illustration: blindfolded Justice holding scales in front of a court building">
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
<!-- figure: original line art of blindfolded Justice in a suit holding scales -->
<g stroke="${INK}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round">
 <path d="M70 440 84 300Q90 255 140 238L200 228 260 238Q310 255 316 300L330 440Z" fill="${SUIT}"/>
 <path d="M200 330 186 300 168 232 232 232 214 300Z" fill="${SHIRT}"/>
 <path d="M168 232 150 262 188 268ZM232 232 250 262 212 268Z" fill="${SHIRT}"/>
 <path d="M188 268 200 330M212 268 200 330" fill="none"/>
 <rect x="182" y="176" width="36" height="58" fill="${SKIN}"/>
 <path d="M184 214q16 12 32 0" fill="none" stroke="${SKIN_SH}" stroke-width="4"/>
 <ellipse cx="160" cy="134" rx="8" ry="13" fill="${SKIN}"/>
 <ellipse cx="200" cy="130" rx="40" ry="52" fill="${SKIN}"/>
 <path d="M158 122Q154 70 200 68 248 70 242 120 236 96 200 94 168 96 158 122Z" fill="${INK}"/>
 <path d="M206 138q8 14-2 18M188 168q12 5 24 0" fill="none"/>
 <path d="M240 142q-4 26-22 36" fill="none" stroke="${SKIN_SH}" stroke-width="4"/>
 <path d="M156 110Q200 102 244 110V136Q200 128 156 136Z" fill="${BAND}"/>
 <path d="M158 120Q132 98 108 84 128 110 118 134 140 118 158 128Z" fill="${BAND}"/>
 <path d="M156 128Q132 150 124 180 146 160 162 136Z" fill="${BAND}"/>
 <circle cx="200" cy="362" r="4" fill="${GOLD}"/><circle cx="200" cy="398" r="4" fill="${GOLD}"/>
 <path d="M296 258Q330 290 344 350 348 366 334 374L288 400 276 380 318 352Q306 312 290 290Z" fill="${SUIT}"/>
 <ellipse cx="278" cy="392" rx="15" ry="11" fill="${SKIN}"/>
 <path d="M84 290Q76 340 88 374 104 386 118 372L156 308 138 292Z" fill="${SUIT}"/>
 <path d="M138 292 156 308 163 299 146 285Z" fill="${SHIRT}"/>
</g>
<!-- scales held up in the raised hand -->
<g stroke="${INK}" stroke-width="2" fill="none" stroke-linecap="round">
 <path d="M160 292V318M98 322 80 372M98 322 116 372M218 314 200 360M218 314 236 360"/>
</g>
<path d="M98 322 218 314" stroke="${GOLD}" stroke-width="6" stroke-linecap="round"/>
<g fill="${GOLD}" stroke="${INK}" stroke-width="2.5">
 <path d="M74 372h48a24 11 0 0 1-48 0zM194 360h48a24 11 0 0 1-48 0z"/><circle cx="160" cy="318" r="6"/>
</g>
<ellipse cx="160" cy="290" rx="14" ry="12" fill="${SKIN}" stroke="${INK}" stroke-width="3"/>
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
