// The head of every panel: the title at the left, the info button (i) next to it, the tools (buttons, small knobs, the light) at the right.
// Use: root.innerHTML = header('Atlas') + ...;  then put the tools into ref(root, 'tools'). The text of the (i) is INFO[title] (web/info.js).
import {INFO} from '../info.js';

export const header = (title) => {
  const text = (INFO[title] || []).map((p) => `<p>${p}</p>`).join('');
  return `<div class="top"><span class="panel-title">${title}</span>` +
    (text ? `<span class="info" tabindex="0">\u{1F6C8}︎<span class="info-tip">${text}</span></span>` : '') +
    `<span class="tools" data-ref="tools"></span></div>`;
};

// The text appears at the (i) when the pointer is over it, inside the screen
document.addEventListener('mouseover', (e) => {
  const icon = e.target.closest && e.target.closest('.info');
  if (!icon) return;
  const tip = icon.querySelector('.info-tip'), r = icon.getBoundingClientRect();
  tip.classList.add('show');
  const w = tip.offsetWidth, h = tip.offsetHeight;
  tip.style.left = Math.max(8, Math.min(r.left, window.innerWidth - w - 8)) + 'px';
  tip.style.top = Math.max(8, Math.min(r.bottom + 6, window.innerHeight - h - 8)) + 'px';
});
document.addEventListener('mouseout', (e) => {
  const icon = e.target.closest && e.target.closest('.info');
  if (icon && !icon.contains(e.relatedTarget)) icon.querySelector('.info-tip').classList.remove('show');
});
