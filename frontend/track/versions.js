import {h} from '/base.js';
import {segmentPath} from '/cues.js';

export function trackVersion(code,track,role) {
  return `<li class="track-sleeve" data-unsigned="${!track.signed_at}">
    <span class="track-rev">V${track.version}</span>
    <div><strong>${h(track.file_name)}</strong><span>质检 #${track.quality_id} · SHA-256 ${h(track.track_hash.slice(0,12))}…</span></div>
    <div class="track-action">
      ${track.signed_at ? `<button type="button" data-vtt="${h(segmentPath(code,'/tracks/'+track.version+'/file'))}"
        data-name="${h(track.file_name)}">下载样本</button><small>已签发 · ${h(track.signed_by)}</small>` :
        role === 'reviewer' ? `<form data-endpoint="/tracks/${track.version}/sign"><button>签发样本</button></form>` :
        '<small>待签发</small>'}</div>
  </li>`;
}
