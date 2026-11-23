import {api,h} from '/base.js';
import {segmentPath,studioHeader} from '/cues.js';
import {qualityPanel} from '/quality/panel.js';
import {trackPanel} from '/track/panel.js';
import {incidentPanel} from '/incidents/panel.js';

const views = {
  quality: ['屏显质检','核对说话人、通道及字幕阅读速度。',qualityPanel],
  tracks: ['字幕样本轨','签发可复核的 WebVTT 锚点样本。',trackPanel],
  incidents: ['超时复盘','逐个复测受影响锚点，复核上屏时限。',incidentPanel],
};
export const extraPages = Object.fromEntries(Object.entries(views).map(([key,[label]]) => [key,label]));

export async function renderExtension(page,outlet,user,store,refresh,message) {
  const [label,copy,load] = views[page];
  const code = store.active.segment.code;
  const body = await load(code,user.role);
  if (!outlet.isConnected) return;
  outlet.innerHTML = `<div class="studio">${studioHeader(label,copy,code,store.rows)}
    <p class="studio-status" role="status">${h(message)}</p>${body}</div>`;
  const status = outlet.querySelector('.studio-status');
  const report = error => { status.textContent = error.message; status.dataset.error = 'true'; };
  outlet.querySelector('[name=segment-select]').onchange = event => {
    store.selected = event.target.value;
    refresh().catch(report);
  };
  for (const form of outlet.querySelectorAll('form[data-endpoint]')) form.onsubmit = async event => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    for (const key of (form.dataset.numeric ?? '').split(' ').filter(Boolean)) data[key] = Number(data[key]);
    const button = event.submitter;
    if (button) button.disabled = true;
    try {
      await api(segmentPath(code,form.dataset.endpoint),form.dataset.method ?? 'POST',data);
      if (outlet.contains(form)) await refresh('业务记录已更新');
    } catch (error) { report(error); }
    finally { if (button) button.disabled = false; }
  };
  for (const button of outlet.querySelectorAll('[data-vtt]')) button.onclick = async () => {
    try {
      const content = await api(button.dataset.vtt);
      const url = URL.createObjectURL(new Blob([content],{type:'text/vtt'}));
      const link = Object.assign(document.createElement('a'),{href:url,download:button.dataset.name});
      link.click();
      setTimeout(() => URL.revokeObjectURL(url),1000);
    } catch (error) { report(error); }
  };
}
