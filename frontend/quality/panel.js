import {api,h} from '/base.js';
import {segmentPath} from '/cues.js';
import {markedCue} from './marks.js';

export async function qualityPanel(code,role) {
  const {cues,scans} = await api(segmentPath(code,'/quality'));
  const latest = scans[0];
  const checks = Object.fromEntries((latest?.result.marks ?? []).map(check => [check.cue_no,check]));
  return `<div class="quality-split">
    <section class="desk"><h2>字幕屏显标注</h2><ol class="quality-marks">${cues.map(cue =>
      markedCue(cue,latest?.stale ? null : checks[cue.cue_no],role)).join('')}</ol></section>
    <aside class="desk quality-aside"><h2>可读性检查</h2>
      ${role === 'operator' ? `<form data-endpoint="/quality/scan" data-numeric="max_chars_per_second">
        <label>阅读上限（字/秒）<input name="max_chars_per_second" min="8" max="30" value="${latest?.max_chars_per_second ?? 16}" type="number" required></label>
        <button>检查当前标注</button></form>` : ''}
      <dl class="quality-tickets">${scans.map(scan => `<div><dt>质检 #${scan.id} · ${scan.max_chars_per_second} 字/秒</dt><dd>
        ${scan.stale ? '标注已改' : scan.reviewed_at ? '已复核' : String(scan.result.failed) + ' 个问题锚点'}
        ${role === 'reviewer' && !scan.stale && !scan.reviewed_at && !scan.result.failed ?
          `<form data-endpoint="/quality/${scan.id}/sign"><button>确认通过</button></form>` : ''}
      </dd></div>`).join('')}</dl>
      <a class="studio-link" href="#tracks">查看字幕轨</a>
      <p>${h(latest ? '质量结果基于当前显示时长和说话人标注。' : '完成标注可生成首张质检单。')}</p>
    </aside></div>`;
}
