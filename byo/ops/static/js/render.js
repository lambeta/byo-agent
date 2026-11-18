function esc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function stamp(iso) {
  if (!iso) return '';
  return String(iso).slice(11, 19);
}

function receiptLine(receipt) {
  if (!receipt) return '';
  const estimate = receipt.estimate ? ' · estimate' : '';
  return esc(receipt.iterations) + ' call(s) · ' + esc(receipt.tool_calls) +
    ' tool(s) · ' + esc(receipt.tokens_in) + ' in / ' + esc(receipt.tokens_out) + ' out · USD ' +
    esc(receipt.usd) + estimate;
}

function stepRow(step) {
  const detail = step.kind === 'tool'
    ? step.tool + '(' + step.args + ') → ' + step.output
    : step.kind === 'llm'
      ? 'iteration ' + step.iteration + ' · ' + step.in + ' in / ' + step.out + ' out · ' +
        (step.model || '') + ' · stop ' + step.call
      : step.kind === 'gate'
        ? step.decision + ' — ' + step.reason
        : step.kind === 'memory_write'
          ? 'kept ' + step.new_facts + ' fact(s)'
          : step.message || '';
  const bad = step.ok === false || step.kind === 'error';
  return '<div class="step ' + (bad ? 'bad' : '') + '">' +
    '<span class="kind">' + esc(step.kind === 'memory_write' ? 'memory' : step.kind) + '</span>' +
    '<span class="detail">' + esc(detail) + '</span>' +
    '<span class="time">' + esc(step.duration_ms || '') + (step.duration_ms ? ' ms' : '') + '</span>' +
    '</div>';
}

function stageChips(turn) {
  const chips = [];
  if (turn.gate) chips.push('<span class="chip" data-stage="gate">gate · ' + esc(turn.gate.decision) + '</span>');
  const loops = (turn.steps || []).filter(function (step) { return step.kind === 'llm'; }).length;
  const tools = (turn.steps || []).filter(function (step) { return step.kind === 'tool'; }).length;
  chips.push('<span class="chip" data-stage="loop">' + loops + ' loop(s)</span>');
  chips.push('<span class="chip" data-stage="tool">' + tools + ' tool(s)</span>');
  chips.push('<span class="chip ' + (turn.state === 'failed' ? 'bad' : 'ok') + '" data-state="' +
    esc(turn.state || 'live') + '">' + esc(turn.state || 'live') + '</span>');
  return '<div class="stages">' + chips.join('') + '</div>';
}

function turnCard(turn) {
  const steps = (turn.steps || []).map(stepRow).join('');
  const receipt = turn.receipt ? '<div class="receipt">' + receiptLine(turn.receipt) + '</div>' : '';
  return '<article class="card">' +
    '<div class="meta"><span>' + esc(stamp(turn.started_at)) + '</span>' +
    '<span>' + esc(turn.source || 'cli') + '</span>' +
    '<span>' + esc(turn.turn_id || 'live') + '</span></div>' +
    stageChips(turn) +
    '<div class="reply"><strong>you ›</strong> ' + esc(turn.user_message) + '</div>' +
    '<div class="steps">' + steps + '</div>' +
    (turn.reply ? '<div class="reply" data-stage="reply"><strong>byo ›</strong> ' + esc(turn.reply) + '</div>' : '') +
    receipt +
    '</article>';
}

function focusCard(turn) {
  return '<div id="live">' + turnCard(turn) + '</div>';
}
