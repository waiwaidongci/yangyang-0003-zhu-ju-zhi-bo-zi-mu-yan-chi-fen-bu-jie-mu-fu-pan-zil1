import {api, h, mount, waitJob} from '/base.js';
import {Repair, Pattern, ms, percent, timecode, segmentPath, cueStore, studioHeader, badge, ledger, statusRail} from '/cues.js';

import {extraPages, renderExtension} from '/extensions.js';

const pages = {segments: '节目单', alignment: '锚点时间轴', diagnosis: '延迟诊断', repair: '补字幕交接', ...extraPages};

function segmentPage(row, anchors, repair, role, rows) {
  const board = rows.map((entry) => `<li class="${entry.code === row.code ? 'focus-segment' : ''}">
      <time>${h(entry.rundown_start.slice(0, 5))}</time>
      <button type="button" class="segment-open" data-select="${h(entry.code)}">
        <strong>${h(entry.segment_title)}</strong><span>${h(entry.code)} · ${entry.duration_ms / 1000} s</span>
      </button>
      ${entry.recording_ref ? badge('源录音就绪') : badge('源录音未挂接', true)}
      <span class="cue-progress">${entry.cue_count} / ${entry.expected_anchors} 锚点</span>
    </li>`).join('');
  return `<div class="studio-grid rundown"><section class="desk"><h2>${h(row.program)}</h2>
      <ol class="run-board">${board}</ol></section>
    <aside class="desk side-desk"><h2>${h(row.segment_title)}</h2>
      <dl class="readout"><dt>播出段号</dt><dd>${h(row.code)}</dd><dt>段内上屏预算</dt><dd>${ms(row.sla_ms)}</dd>
      <dt>抽样覆盖</dt><dd>${anchors.length} / ${row.expected_anchors}</dd><dt>原始录音</dt><dd>${h(row.recording_ref ?? '待归档')}</dd></dl>
      ${role === 'operator' && !['submitted', 'accepted'].includes(repair?.status) ?
        `<form data-action="recording"><label>源录音文件名<input name="recording_ref" required placeholder="可填写 .wav 或 .flac" value="${h(row.recording_ref ?? '')}"></label>
        <button>挂接录音</button></form>` : ''}
      <a class="studio-link" href="#alignment">查看时间码锚点</a>
    </aside></div>`;
}

function alignmentPage(row, anchors, repair, role) {
  const timeline = anchors.map((cue) => {
    const delay = cue.on_air_ms - cue.spoken_ms;
    return `<button type="button" data-cue="${cue.cue_no}" class="cue-mark ${delay > row.sla_ms ? 'is-late' : ''}"
       style="--tick:${cue.spoken_ms / row.duration_ms * 100}%"
       aria-label="${h(timecode(cue.spoken_ms) + ' ' + cue.excerpt)}" title="${h(cue.excerpt)}">${cue.cue_no}</button>`;
  }).join('');
  const next = Array.from({length: row.expected_anchors}, (_, index) => index + 1)
    .find((number) => !anchors.some((cue) => cue.cue_no === number)) ?? 1;
  return `<div class="alignment-stack"><section class="desk track-desk">
    <div class="track-legend"><h2>语音时间轴</h2><span>点选编号加载锚点</span></div>
    <div class="cue-track">${timeline}</div>
    <div class="time-poles"><span>00:00.000</span><span>${timecode(Math.floor(row.duration_ms / 2))}</span><span>${timecode(row.duration_ms)}</span></div>
    </section><div class="studio-grid">
    <section class="desk">${ledger(['编号', '语音', '上屏', '抽样字幕', '差值'], anchors.map((cue) => [
      String(cue.cue_no), timecode(cue.spoken_ms), timecode(cue.on_air_ms), h(cue.excerpt),
      cue.on_air_ms - cue.spoken_ms > row.sla_ms ? badge(ms(cue.on_air_ms - cue.spoken_ms), true) : ms(cue.on_air_ms - cue.spoken_ms),
    ]), '对齐清单')}</section>
    <aside class="desk side-desk"><h2>登记抽样锚点</h2>
    ${role === 'operator' && !['submitted', 'accepted'].includes(repair?.status) ?
      `<form data-action="alignment"><label>抽样编号<input name="cue_no" type="number" required min="1" max="${row.expected_anchors}" value="${next}"></label>
      <div class="time-fields"><label>语音时间 ms<input name="spoken_ms" type="number" min="0" max="${row.duration_ms}" required></label>
      <label>上屏时间 ms<input name="on_air_ms" type="number" min="0" max="${row.duration_ms}" required></label></div>
      <label>字幕摘句<input name="excerpt" maxlength="100" required placeholder="从该节目段摘录一句"></label><button>保存锚点</button></form>` :
      '<p>当前角色或工作包状态下可查看锚点。</p>'}</aside></div></div>`;
}

function ecdfPlot(result, sla) {
  const first = Math.min(0, result.ecdf[0].offset_ms);
  const extent = Math.max(sla + 1000, result.ecdf.at(-1).offset_ms + 500);
  const xAt = (x) => (x - first) / (extent - first) * 100;
  let prevX = first;
  let prevY = 0;
  const lines = result.ecdf.map((point) => {
    const x = xAt(point.offset_ms);
    const y = point.share * 100;
    const stroke = `<i class="ecdf-x" style="left:${xAt(prevX)}%;width:${x - xAt(prevX)}%;bottom:${prevY}%"></i>
      <i class="ecdf-y" style="left:${x}%;bottom:${prevY}%;height:${y - prevY}%"></i>`;
    prevX = point.offset_ms;
    prevY = y;
    return stroke;
  }).join('');
  return `<figure class="ecdf"><figcaption>经验累计分布 · 延迟不超过横轴值的字幕比例</figcaption>
    <div class="ecdf-plot" role="img" aria-label="字幕延迟ECDF，九十分位 ${ms(result.p90)}">
      <span class="chart-label top">100%</span><span class="chart-label middle">50%</span><span class="chart-label bottom">0%</span>
      <i class="sla-line" style="left:${xAt(sla)}%"><b>时限 ${ms(sla)}</b></i>${lines}
      <i class="ecdf-x" style="left:${xAt(prevX)}%;width:${100 - xAt(prevX)}%;bottom:100%"></i>
    </div><div class="time-poles"><span>${ms(first)}</span><span>${ms(extent)}</span></div>
  </figure>`;
}

const ReleaseState = {computing: '后台重算中', published: '已生效', failed: '已失败，整档保留旧版'};
const ReleaseSegment = {pending: '待重算', done: '已就绪', failed: '失败'};
const requestKey = () => globalThis.crypto?.randomUUID?.() ??
  `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

async function waitRelease(program, maxWait = 15000) {
  const deadline = Date.now() + maxWait;
  do {
    const {release} = await api(`/api/programs/${encodeURIComponent(program)}/sla`);
    if (!release || release.status !== 'computing') return release?.status ?? 'none';
    await new Promise((resolve) => setTimeout(resolve, 400));
  } while (Date.now() < deadline);
  return 'computing';
}

function releaseSection(status, row, role) {
  const release = status?.release;
  const segments = status?.segments ?? [];
  const panel = release ? `<dl class="readout">
      <dt>目标时限</dt><dd>${ms(release.sla_ms)}</dd>
      <dt>发布进度</dt><dd>${ReleaseState[release.status]} · ${release.done}/${release.total} 段</dd>
      ${release.published_at ? `<dt>切换时间</dt><dd>${new Date(release.published_at).toLocaleString('zh-CN')}</dd>` : ''}
      ${release.error ? `<dt>保留旧版原因</dt><dd>${h(release.error)}</dd>` : ''}</dl>
      <ul class="repair-checks">${segments.map((seg) => `<li>
        ${badge(ReleaseSegment[seg.status] ?? seg.status, seg.status !== 'done')} <span>${h(seg.segment_code)}</span>
      </li>`).join('')}</ul>` :
    '<p>暂无时限调整发布，当前时限逐段生效。</p>';
  const form = role === 'operator' && release?.status !== 'computing' ? `
    <form data-action="sla" data-request-key="${requestKey()}">
      <label>整档新时限 ms<input name="sla_ms" type="number" min="250" max="8000" step="50" value="${row.sla_ms}" required></label>
      <button>整档调整时限</button>
      <p>对「${h(row.program)}」全部节目段按新时限后台重算，齐了再一次切换。</p>
    </form>` : '';
  const refresh = release?.status === 'computing' ?
    '<form data-action="refresh"><button>刷新发布进度</button></form>' : '';
  return `<aside class="desk side-desk release-desk"><h2>整档时限发布</h2>${panel}${form}${refresh}</aside>`;
}

function diagnosisPage(row, anchors, repair, role, rows, releaseStatus) {
  const result = row.diagnosis;
  const current = result && row.diagnosis_revision === row.anchor_revision;
  const actions = role === 'operator' ? `<form data-action="diagnosis"><button ${anchors.length < 5 ? 'disabled' : ''}>生成当前版本诊断</button></form>` : '';
  if (!result) return `<div class="studio-grid"><section class="desk"><h2>等待对齐数据</h2>
    <p>收齐至少 5 个锚点后可生成延迟分布。</p><a class="studio-link" href="#alignment">前往锚点时间轴</a>${actions}</section>
    ${releaseSection(releaseStatus, row, role)}</div>`;
  return `<div class="studio-grid"><section class="desk diag-plot">
      <div class="track-legend"><h2>延迟分布</h2>${current ? badge('锚点版本 ' + row.anchor_revision) : badge('锚点已更新，请重新诊断', true)}</div>
      ${ecdfPlot(result, row.sla_ms)}
      <div class="window-counts">${result.late_windows.map((count, i) => `<div><span>第 ${i + 1} 段</span><strong>${count}</strong><span>条超时</span></div>`).join('')}</div>
    </section><aside class="desk side-desk"><h2>${Pattern[result.pattern]}</h2>
      <dl class="readout"><dt>当前生效时限</dt><dd>${ms(row.sla_ms)}</dd>
      <dt>中位延迟</dt><dd>${ms(result.p50)}</dd><dt>90 分位延迟</dt><dd>${ms(result.p90)}</dd>
      <dt>超标比例</dt><dd>${percent(result.late_rate)} · ${result.late_count}/${result.count}</dd>
      <dt>抽样覆盖</dt><dd>${percent(result.coverage)}</dd>
      <dt>超标锚点</dt><dd>${result.late_cues.length ? result.late_cues.join('、') : '无'}</dd></dl>
      ${actions}
      ${current && result.repair_range && !repair && role === 'operator' ? '<form data-action="open"><button>派发补字幕</button></form>' : ''}
      ${repair ? '<a class="studio-link" href="#repair">查看交接</a>' : ''}
    </aside>${releaseSection(releaseStatus, row, role)}</div>`;
}

function repairPage(row, anchors, repair, role) {
  const submitted = repair?.status === 'submitted';
  const canEdit = role === 'operator';
  return `<div class="studio-grid"><section class="desk repair-desk"><h2>补字幕校对单</h2>${statusRail(repair)}
      ${repair ? `<div class="repair-range">
        <span>回查时间码</span><strong>${timecode(repair.start_ms)} → ${timecode(repair.end_ms)}</strong>
        <span>以相对节目段起点为准</span></div>
        <dl class="readout"><dt>补字幕文件</dt><dd>${h(repair.corrected_ref ?? '待交回')}</dd>
        <dt>校对说明</dt><dd>${h(repair.review_note ?? '暂无')}</dd>
        ${repair.reviewed_by ? `<dt>复核人</dt><dd>${h(repair.reviewed_by)}</dd>` : ''}</dl>` :
        '<p>当前节目段暂无补字幕工作包。</p><a class="studio-link" href="#diagnosis">从超标时段派发补字幕</a>'}
      ${repair?.status === 'queued' && canEdit ? '<form data-action="start"><button>领取时间码范围</button></form>' : ''}
      ${repair?.status === 'editing' && canEdit ? `<form data-action="submit">
        <label>补字幕文件名<input name="corrected_ref" placeholder="可填写 .vtt 或 .srt" value="${h(repair.corrected_ref ?? '')}" required></label>
        <button>送复核签收</button></form>` : ''}
      ${submitted && role === 'reviewer' ? '<form data-action="accept"><label>复核说明<input name="note"></label><button>签收补字幕</button><button type="submit" name="return">退回修改</button></form>' : ''}
    </section><aside class="desk side-desk"><h2>签收条件</h2>
      <ul class="repair-checks">
        <li>${badge(row.recording_ref ? '已挂接' : '需补录', !row.recording_ref)} <a href="#segments">原始录音</a><span>${h(row.recording_ref ?? '交接前挂接节目源文件')}</span></li>
        <li>${badge(anchors.length * 5 >= row.expected_anchors * 4 ? '已达标' : '覆盖不足', anchors.length * 5 < row.expected_anchors * 4)} <a href="#alignment">锚点覆盖</a><span>${anchors.length} / ${row.expected_anchors}（至少 80%）</span></li>
      </ul></aside></div>`;
}

const views = {segments: segmentPage, alignment: alignmentPage, diagnosis: diagnosisPage, repair: repairPage};
const copy = {
  segments: '核对直播段、源录音归档和计划抽样数。',
  alignment: '逐句比对语音起点与字幕上屏时间。',
  diagnosis: '按时限查找迟到集中在哪段，并定位需补字幕的范围。',
  repair: '领取回查区间、送补字幕文件复核、签收归档。',
};

async function render(page, outlet, user, message = '') {
  const store = await cueStore.load();
  if (!store.active) {
    outlet.innerHTML = '<p>暂无已登记的直播节目段。</p>';
    return;
  }
  if (Object.hasOwn(extraPages,page)) {
    return renderExtension(page,outlet,user,store,(updated='') => render(page,outlet,user,updated),message);
  }
  const {segment: row, anchors, repair} = store.active;
  const releaseStatus = page === 'diagnosis' ?
    await api(`/api/programs/${encodeURIComponent(row.program)}/sla`) : null;
  outlet.innerHTML = `<div class="studio">
    ${studioHeader(pages[page], copy[page], row.code, store.rows)}
    <p class="studio-status" role="status" aria-live="polite">${h(message)}</p>
    ${views[page](row, anchors, repair, user.role, store.rows, releaseStatus)}
  </div>`;
  function choose(code) {
    cueStore.selected = code;
    render(page, outlet, user).catch((error) => outlet.querySelector('.studio-status').textContent = error.message);
  }
  outlet.querySelector('[name="segment-select"]').onchange = (event) => choose(event.target.value);
  for (const button of outlet.querySelectorAll('button[data-select]')) button.onclick = () => choose(button.dataset.select);
  for (const button of outlet.querySelectorAll('button[data-cue]')) button.onclick = () => {
    const anchor = anchors.find((entry) => entry.cue_no === Number(button.dataset.cue));
    const form = outlet.querySelector('[data-action="alignment"]');
    if (form) {
      for (const key of ['cue_no', 'spoken_ms', 'on_air_ms', 'excerpt']) form.elements[key].value = anchor[key];
      form.elements.spoken_ms.focus();
    } else {
      outlet.querySelector('.studio-status').textContent = `锚点 ${anchor.cue_no} · ${anchor.excerpt}`;
    }
  };
  for (const form of outlet.querySelectorAll('form[data-action]')) form.onsubmit = async (event) => {
    event.preventDefault();
    const status = outlet.querySelector('.studio-status');
    const action = event.submitter?.name === 'return' ? 'return' : form.dataset.action;
    const fields = Object.fromEntries(new FormData(form));
    const button = event.submitter;
    if (button) button.disabled = true;
    status.textContent = '正在处理…';
    try {
      if (action === 'alignment') {
        for (const name of ['cue_no', 'spoken_ms', 'on_air_ms']) fields[name] = Number(fields[name]);
        await api(segmentPath(row.code, '/alignment'), 'PUT', fields);
      } else if (action === 'recording') {
        await api(segmentPath(row.code, '/recording'), 'PUT', fields);
      } else if (action === 'diagnosis') {
        const {job_id} = await api(segmentPath(row.code, '/diagnosis'), 'POST');
        const result = await waitJob(job_id);
        if (result.stale) throw new Error('锚点版本已更新，请重新生成诊断');
      } else if (action === 'sla') {
        fields.sla_ms = Number(fields.sla_ms);
        fields.request_key = form.dataset.requestKey;
        await api(`/api/programs/${encodeURIComponent(row.program)}/sla`, 'POST', fields);
        const outcome = await waitRelease(row.program);
        if (outlet.contains(form)) await render(page, outlet, user,
          outcome === 'published' ? '整档时限已切换生效' :
          outcome === 'failed' ? '时限发布失败，整档保留旧版诊断' : '后台仍在重算，可稍后刷新进度');
        return;
      } else if (action === 'refresh') {
        if (outlet.contains(form)) await render(page, outlet, user, '已刷新发布进度');
        return;
      } else if (action === 'open') {
        await api(segmentPath(row.code, '/repair'), 'POST');
      } else {
        await api(segmentPath(row.code, `/repair/${action}`), 'POST', fields);
      }
      if (outlet.contains(form)) await render(page, outlet, user, '已保存');
    } catch (error) {
      status.textContent = error.message;
      status.dataset.error = 'true';
    } finally {
      if (button) button.disabled = false;
    }
  };
}

mount({title:'逐句', kicker:'街巷广播编辑室', pages, render});
