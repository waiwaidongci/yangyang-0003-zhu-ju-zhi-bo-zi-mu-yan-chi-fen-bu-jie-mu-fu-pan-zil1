import {h} from '/base.js';
import {timecode} from '/cues.js';

const channels = {host:'主持人声',guest:'现场嘉宾',remote:'远程连线'};
export const issues = {missing_mark:'待标说话人',crowded_text:'阅读速度过高',beyond_segment:'超出段尾',overlap:'字幕重叠'};
export function markedCue(cue, check, role) {
  const entries = check?.issues.map(key => issues[key]) ?? [];
  return `<li class="mark-row"><div>
    <small>锚点 ${cue.cue_no} · ${timecode(cue.on_air_ms)}</small><strong>${h(cue.excerpt)}</strong>
    <span>${check?.chars_per_second ?? '—'} 字/秒</span>
    <span class="mark-issues">${entries.map(item => `<span>${h(item)}</span>`).join('')}</span></div>
    ${role === 'operator' ? `<form class="mark-edit" data-endpoint="/quality/marks/${cue.cue_no}" data-method="PUT" data-numeric="display_ms">
      <label>通道<select name="channel">${Object.entries(channels).map(([key,name]) =>
        `<option value="${key}" ${cue.channel === key ? 'selected' : ''}>${name}</option>`).join('')}</select></label>
      <label>说话人<input name="speaker" value="${h(cue.speaker)}" maxlength="40" required></label>
      <label>显示毫秒<input name="display_ms" min="250" max="15000" type="number" value="${cue.display_ms ?? 1700}" required></label>
      <button>存标注</button></form>` : `<p>${h(channels[cue.channel] ?? '未标')} · ${h(cue.speaker ?? '待确认')}</p>`}
  </li>`;
}
