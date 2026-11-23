import {api} from '/base.js';
import {segmentPath} from '/cues.js';
import {trackVersion} from './versions.js';

export async function trackPanel(code,role) {
  const {tracks,quality_choices:choices} = await api(segmentPath(code,'/tracks'));
  return `<div class="track-layout"><section class="desk"><h2>样本字幕轨卷宗</h2>
    ${tracks.length ? `<ol class="track-versions">${tracks.map(item => trackVersion(code,item,role)).join('')}</ol>` :
     '<p>本节目段暂无字幕轨。确认质检后可编制首版。</p>'}</section>
    <aside class="desk track-source"><h2>编制来源</h2>
    <p>样本轨使用已通过质检的节目锚点和说话人标注。有补字幕工作包时，签收后才可编制。</p>
    ${role === 'operator' && choices.length ? `<form data-endpoint="/tracks" data-numeric="quality_id">
      <label>引用质检单<select name="quality_id">${choices.map(choice => `<option value="${choice.id}">#${choice.id}</option>`).join('')}</select></label>
      <button>编制新版本</button></form>` : ''}
    <a class="studio-link" href="#quality">核对显示和说话人</a></aside></div>`;
}
