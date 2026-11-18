function pct(value, max) {
  if (!max) return 0;
  return Math.max(2, Math.round((value / max) * 100));
}

function turnTrack(turn) {
  const steps = (turn.steps || []).filter(function (step) { return step.duration_ms; });
  const max = steps.reduce(function (acc, step) { return Math.max(acc, step.duration_ms || 0); }, 0);
  if (!steps.length) return '<div class="turnbar"><span>' + esc(turn.turn_id) + '</span><span class="empty">no timed steps</span></div>';
  const bars = steps.map(function (step) {
    return '<span title="' + esc(step.kind) + ' ' + esc(step.duration_ms) + ' ms" style="left:' +
      (step.ts ? 0 : 0) + '%;width:' + pct(step.duration_ms, max) + '%"></span>';
  }).join('');
  return '<div class="turnbar"><span>' + esc(turn.turn_id) + '</span><span class="track">' + bars + '</span></div>';
}

function observeView(data) {
  const turns = data.turns || [];
  const spend = data.spend || { total_usd: 0, by_model: [] };
  const toolCount = (data.tools || []).filter(function (step) { return step.kind === 'tool'; }).length;
  const stats = '<div class="grid">' +
    '<div class="card"><div class="meta">turns</div><div class="stat">' + turns.length + '</div></div>' +
    '<div class="card"><div class="meta">tool calls</div><div class="stat">' + toolCount + '</div></div>' +
    '<div class="card"><div class="meta">spend</div><div class="stat">$ ' + esc(spend.total_usd) + '</div></div>' +
    '</div>';
  const byModel = (spend.by_model || []).map(function (row) {
    return '<tr><td>' + esc(row.model) + '</td><td>$ ' + esc(row.usd) + '</td></tr>';
  }).join('');
  const list = turns.length
    ? turns.map(turnTrack).join('')
    : '<p class="empty">No turns recorded yet.</p>';
  return '<h1>Observability</h1>' + stats +
    '<section class="card"><h1>Turns</h1>' + list + '</section>' +
    '<section class="card"><h1>Spend by model</h1><table><tr><th>model</th><th>USD</th></tr>' +
    (byModel || '<tr><td colspan="2" class="empty">nothing spent yet</td></tr>') + '</table></section>';
}
