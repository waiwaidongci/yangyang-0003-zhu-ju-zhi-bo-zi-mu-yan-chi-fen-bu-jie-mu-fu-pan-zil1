import {api} from '/base.js';
import {segmentPath} from '/cues.js';
import {causes,replayCard} from './retests.js';

export async function incidentPanel(code,role) {
  const {incidents,tracks} = await api(segmentPath(code,'/incidents'));
  return `<div class="incident-layout"><section class="replay-ledger">
    ${incidents.length ? incidents.map(row => replayCard(row,role)).join('') : '<div class="desk"><h2>暂无超时复盘</h2><p>当前诊断和已签样本轨可作为复测依据。</p></div>'}</section>
    <aside class="desk"><h2>受影响区间复测</h2>
    ${role === 'operator' && tracks.length ? `<form data-endpoint="/incidents" data-numeric="track_version">
      <label>签发样本轨<select name="track_version">${tracks.map(track => `<option value="${track.version}">V${track.version}</option>`).join('')}</select></label>
      <label>问题类型<select name="cause">${Object.entries(causes).map(([key,label]) => `<option value="${key}">${label}</option>`).join('')}</select></label>
      <label>改进措施<textarea name="countermeasure" rows="3" minlength="6" maxlength="300" required></textarea></label>
      <button>登记复盘事件</button></form>` : ''}
    <a class="studio-link" href="#diagnosis">回查时限诊断</a>
    </aside></div>`;
}
