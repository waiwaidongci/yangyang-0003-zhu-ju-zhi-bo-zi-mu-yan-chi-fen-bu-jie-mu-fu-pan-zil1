import {h} from '/base.js';
import {ms} from '/cues.js';

export const causes = {monitoring:'返听监测',latency_queue:'上屏积压',missing_context:'缺上下文',handoff:'岗位交接'};

export function replayCard(row,role) {
  const completed = Object.fromEntries(row.checks.map(check => [check.cue_no,check.replay_delay_ms]));
  return `<article class="desk replay-card"><h2>${causes[row.cause]} · 事件 #${row.id}</h2>
    <p>${h(row.countermeasure)}</p>
    <p>轨道 V${row.track_version} · 锚点版本 ${row.source_revision} · 上屏预算 ${ms(row.sla_ms)}</p>
    <ul class="replay-list">${row.impacted_cues.map(cue => `<li>
      <strong>锚点 ${cue}</strong><span data-late="${row.late.includes(cue)}">${completed[cue] === undefined ?
      '待复测' : ms(completed[cue])}</span>
      ${role === 'operator' && !row.closed_at ? `<form data-endpoint="/incidents/${row.id}/retest/${cue}"
        data-method="PUT" data-numeric="replay_delay_ms"><label>回放延迟（ms）<input name="replay_delay_ms"
        value="${completed[cue] ?? ''}" min="0" max="30000" type="number" required></label><button>记入</button></form>` : ''}
    </li>`).join('')}</ul>
    ${row.closed_at ? `<p>已结案 · ${h(row.closed_by)}</p>` : role === 'reviewer' ?
      `<form data-endpoint="/incidents/${row.id}/close"><button>签复盘结论</button></form>` : '<p>全部受影响锚点达标后送复核结案。</p>'}
  </article>`;
}
