// Colours that canvases need. Everything else about the look is in theme.css: the colours of the page are its
// variables, read here once, so a canvas and the page can never disagree.

// The side of the square canvases (semantic playground, structure playground, atlas), in px. The panels and the page follow it:
// 520 is the roomy size; 480 fits a 1080p screen without scrolling.
export const CANVAS = 480;

// The colours of the semantic sources and their dots (32), from the track and clip palette of Ableton Live (its two main rows),
// ordered so that neighbours differ; the last six are muted versions for the rare atlas with more than 26 clusters.
// To change the colours of everything that follows a cluster (blocks, dots, atlas points, regions), change this list.
export const PALETTE = ["#FF3636", "#19E9FF", "#F7F47C", "#886CE4", "#3DC300", "#FFA529", "#5480E4", "#E553A0",
  "#BFFB00", "#00BFAF", "#CC9927", "#D86CE4", "#FF94A6", "#25FFA8", "#10A4EE", "#F66C03",
  "#92A7FF", "#87FF67", "#99724B", "#B677C6", "#FF39D4", "#8BC5FF", "#1AFF2F", "#5CFFE8",
  "#007DC0", "#FFF034", "#C75A6B", "#4FA86F", "#B59A3A", "#6B7FA8", "#9C6BA8", "#6B9C9C"];

// The variables of theme.css that canvases use, as {name: value}.
export function readTheme(root) {
  const style = getComputedStyle(root);
  const v = (name) => style.getPropertyValue(name).trim();
  return {bg: v('--bg'), panel: v('--panel'), zone: v('--zone'), text: v('--text'), line: v('--line'),
          accent: v('--accent'), accentSoft: v('--accent-soft'), accentFaint: v('--accent-faint'), font: v('--font')};
}

// Adds a stylesheet to the page once; resolves when it has loaded.
export function loadCss(href) {
  return new Promise((resolve) => {
    if (document.querySelector(`link[href^="${href}"]`)) { resolve(); return; }
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href + '?v=' + Date.now();
    link.onload = link.onerror = () => resolve();
    document.head.appendChild(link);
  });
}
