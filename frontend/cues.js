import {api, h} from '/base.js';

export const Repair = { queued: '待接单', editing: '补录中', submitted: '待签收', accepted: '已签收' };
export const Pattern = { local_tail: '集中掉队', systematic: '整体偏慢', sporadic: '个别超时', on_time: '准时' };
export const ms = (value) => `${Number(value).toLocaleString('zh-CN')} ms`;
export const percent = (value) => `${Math.round(value * 100)}%`;
export const timecode = (value) =>
  `${String(Math.floor(value / 60000)).padStart(2, '0')}:${String(Math.floor(value / 1000) % 60).padStart(2, '0')}.${String(value % 1000).padStart(3, '0')}`;
export const segmentPath = (code, path = '') => `/api/rundown/${encodeURIComponent(code)}${path}`;

export const cueStore = {
  selected: null,
  async load() {
    this.rows = await api('/api/rundown');
    this.selected ??= this.rows[0]?.code;
    this.active = this.selected ? await api(segmentPath(this.selected)) : null;
    return this;
  },
};

export function studioHeader(title, subtitle, code, segments) {
  return `<div class="studio-head"><div><h1>${h(title)}</h1><p>${h(subtitle)}</p></div>
    <label class="segment-picker">节目段<select name="segment-select" aria-label="节目段">
      ${segments.map((row) => `<option value="${h(row.code)}" ${row.code === code ? 'selected' : ''}>${h(row.segment_title)} · ${h(row.code)}</option>`).join('')}
    </select></label></div>`;
}

export function badge(label, warning = false) {
  return `<span class="cue-badge ${warning ? 'warning' : ''}">${h(label)}</span>`;
}

export function ledger(headers, rows, caption) {
  return `<div class="ledger-scroll"><table class="cue-ledger"><caption>${h(caption)}</caption>
    <thead><tr>${headers.map((header) => `<th scope="col">${h(header)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>
    </table></div>`;
}

export function statusRail(repair) {
  return `<ol class="status-rail">${Object.entries(Repair).map(([key, label]) =>
    `<li ${repair?.status === key ? 'aria-current="step"' : ''}>${label}</li>`).join('')}</ol>`;
}
