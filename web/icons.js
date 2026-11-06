/* TabDock line icons (24×24, stroke 1.8, round caps) — drawn for this project, no emoji. */
"use strict";
const ICONS = {
  home: '<path d="M3.5 10.5 12 4l8.5 6.5"/><path d="M5.5 9v10.5h13V9"/><path d="M10 19.5v-5h4v5"/>',
  aperture: '<circle cx="12" cy="12" r="8.5"/><path d="m9.5 3.9 5.3 9.1M17.9 6.4l-5.3 9.1M20.4 12H9.9M14.5 20.1 9.2 11M6.1 17.6l5.3-9.1M3.6 12h10.5"/>',
  book: '<path d="M4.5 5.5c2.5-1.3 5-1.3 7.5 0v14c-2.5-1.3-5-1.3-7.5 0z"/><path d="M12 5.5c2.5-1.3 5-1.3 7.5 0v14c-2.5-1.3-5-1.3-7.5 0"/>',
  computer: '<rect x="3.5" y="4.5" width="17" height="11.5" rx="2"/><path d="M9 20h6M12 16v4"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.4M12 18.8v2.4M21.2 12h-2.4M5.2 12H2.8M18.5 5.5l-1.7 1.7M7.2 16.8l-1.7 1.7M18.5 18.5l-1.7-1.7M7.2 7.2 5.5 5.5"/>',
  cup: '<path d="M5 9h11v5a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5z"/><path d="M16 10.5h1.5a2.5 2.5 0 0 1 0 5H16"/><path d="M8.5 3.5c0 1.5 1.5 1.5 1.5 3M12.5 3.5c0 1.5 1.5 1.5 1.5 3"/>',
  expand: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  qr: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><path d="M14 14h2v2h-2zM18 14h2M14 18v2M18 18h2v2"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  star: '<path d="m12 4 2.4 5 5.4.7-4 3.8 1 5.4L12 16.3 7.2 18.9l1-5.4-4-3.8 5.4-.7z"/>',
  calendar: '<rect x="4" y="5.5" width="16" height="14.5" rx="2.5"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  chevron: '<path d="m9.5 6 6 6-6 6"/>',
  alert: '<path d="M12 4.5 2.8 19.5h18.4z"/><path d="M12 10v4.5M12 17.2v.1"/>',
  drive: '<rect x="3.5" y="13" width="17" height="6.5" rx="2"/><path d="M5.5 13 8 5.5h8l2.5 7.5"/><path d="M16.5 16.3h.1"/>',
  archive: '<rect x="3.5" y="4.5" width="17" height="4.5" rx="1.3"/><path d="M5 9v9.5a1.5 1.5 0 0 0 1.5 1.5h11a1.5 1.5 0 0 0 1.5-1.5V9M10 13h4"/>',
  hourglass: '<path d="M7 3.5h10M7 20.5h10M8 3.5c0 5 8 5 8 8.5s-8 3.5-8 8.5M16 3.5c0 5-8 5-8 8.5s8 3.5 8 8.5"/>',
  drop: '<path d="M12 3.8c3.3 4 5.5 7 5.5 9.7a5.5 5.5 0 0 1-11 0c0-2.7 2.2-5.7 5.5-9.7z"/>',
  note: '<path d="M9 17.5V6l10-2v11.5"/><circle cx="6.5" cy="17.5" r="2.5"/><circle cx="16.5" cy="15.5" r="2.5"/>',
  prev: '<path d="M7 5.5v13M18 6l-8.5 6 8.5 6z"/>',
  next: '<path d="M17 5.5v13M6 6l8.5 6L6 18z"/>',
  play: '<path d="M8 5.5v13l10.5-6.5z"/>',
  pause: '<path d="M8.5 5.5v13M15.5 5.5v13"/>',
  volume: '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>',
  mute: '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="m16 9.5 5 5M21 9.5l-5 5"/>',
  frame: '<path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16"/><circle cx="12" cy="12" r="3"/>',
  moon: '<path d="M19.5 14.5A7.5 7.5 0 0 1 9.5 4.5a7.5 7.5 0 1 0 10 10z"/>',
  display: '<rect x="3.5" y="4.5" width="17" height="11.5" rx="2"/><path d="M9 20h6M12 16v4M8 12.5l8-5"/>',
  app: '<rect x="4.5" y="4.5" width="15" height="15" rx="4"/>',
  disc: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="2.5"/>',
  folder: '<path d="M3.5 7.5A1.5 1.5 0 0 1 5 6h4.5l2 2.5H19a1.5 1.5 0 0 1 1.5 1.5v8A1.5 1.5 0 0 1 19 19.5H5A1.5 1.5 0 0 1 3.5 18z"/>',
  eject: '<path d="M12 5 5 13.5h14z"/><path d="M5 18.5h14"/>',
  pin: '<path d="M9 4h6l-1 6 3.5 3.5h-11L10 10z"/><path d="M12 13.5V20"/>',
  pencil: '<path d="M4.5 19.5 5.5 15 15.5 5a2.1 2.1 0 0 1 3 3l-10 10z"/><path d="m13.5 7 3 3"/>',
  reset: '<path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3"/><path d="M4.5 4.5v4h4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.8v2M12 19.2v2M21.2 12h-2M4.8 12h-2M18.5 5.5l-1.4 1.4M6.9 17.1l-1.4 1.4M18.5 18.5l-1.4-1.4M6.9 6.9 5.5 5.5"/>',
  cloudsun: '<path d="M8.5 7.5a3.5 3.5 0 0 1 6.4-1.2M12 2.5v1.5M5 4.5l1 1M3 10h1.5"/><path d="M7.5 19.5h9.5a3.5 3.5 0 0 0 .4-7 5 5 0 0 0-9.6 1.5 2.8 2.8 0 0 0-.3 5.5z"/>',
  cloud: '<path d="M7 18.5h10.5a4 4 0 0 0 .5-8 6 6 0 0 0-11.5 1.8A3.2 3.2 0 0 0 7 18.5z"/>',
  fog: '<path d="M6 10.5a6 6 0 0 1 11.5-1.5M4 14h16M6 17.5h12M8 21h8"/>',
  rain: '<path d="M7 15h10.5a4 4 0 0 0 .5-8 6 6 0 0 0-11.5 1.8A3.2 3.2 0 0 0 7 15z"/><path d="m9 18-1 2.5M13 18l-1 2.5M17 18l-1 2.5"/>',
  snow: '<path d="M7 15h10.5a4 4 0 0 0 .5-8 6 6 0 0 0-11.5 1.8A3.2 3.2 0 0 0 7 15z"/><path d="M9 18.5h.1M12 20.5h.1M15 18.5h.1"/>',
  storm: '<path d="M7 14.5h10.5a4 4 0 0 0 .5-8 6 6 0 0 0-11.5 1.8A3.2 3.2 0 0 0 7 14.5z"/><path d="m12.5 15.5-2 3.5h3l-2 3"/>',
};
function ic(name, cls) {
  return `<svg class="i ${cls || ""}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.app}</svg>`;
}
function weatherIcon(code) {
  code = +code || 0;
  if (code === 0) return "sun";
  if (code <= 2) return "cloudsun";
  if (code === 3) return "cloud";
  if (code === 45 || code === 48) return "fog";
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return "snow";
  if (code >= 95) return "storm";
  return "rain";
}
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-ic]").forEach((el) => { el.innerHTML = ic(el.dataset.ic) + el.innerHTML; });
});
