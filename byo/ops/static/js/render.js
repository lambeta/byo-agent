function esc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// A small Markdown renderer for replies. Mechanism: escape the whole string first,
// then turn a fixed subset into tags (paragraphs, line breaks, headings, lists with
// nesting and task boxes, quotes, rules, fenced code, inline code, bold, italic,
// links, images, pipe tables). Links keep http(s)/mailto targets and images keep
// http(s) sources; raw HTML never survives escaping.
// Rejected alternative: a Markdown library. It would add a dependency and a build
// step to a page that must render offline with no bundler.
function mdInline(text) {
  const codes = [];
  let out = text.replace(/`([^`\n]+)`/g, function (match, code) {
    codes.push(code);
    return '\u0000C' + (codes.length - 1) + '\u0000';
  });
  out = out.replace(/!\[([^\]\n]*)\]\((https?:[^)\s]+)\)/g,
    '<img src="$2" alt="$1" loading="lazy">');
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  out = out.replace(
    /\[([^\]\n]+)\]\((https?:|mailto:)([^)\s]+)\)/g,
    '<a href="$2$3" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  out = out.replace(/\u0000C(\d+)\u0000/g, function (match, index) {
    return '<code>' + codes[Number(index)] + '</code>';
  });
  return out;
}

function mdIndent(line) {
  return line.match(/^[ \t]*/)[0].replace(/\t/g, '    ').length;
}

function mdItem(line) {
  const match = line.match(/^([ \t]*)([-*+]|\d+[.)])\s+(.*)$/);
  if (!match) return null;
  return { indent: mdIndent(line), ordered: /\d/.test(match[2]), text: match[3] };
}

function mdCells(line) {
  let text = line.trim();
  if (text.charAt(0) === '|') text = text.slice(1);
  if (text.charAt(text.length - 1) === '|') text = text.slice(0, -1);
  const cells = [];
  let current = '';
  let inCode = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text.charAt(index);
    if (char === '`') {
      inCode = !inCode;
      current += char;
      continue;
    }
    if (!inCode && char === '\\' && text.charAt(index + 1) === '|') {
      current += '|';
      index += 1;
      continue;
    }
    if (!inCode && char === '|') {
      cells.push(current);
      current = '';
      continue;
    }
    current += char;
  }
  cells.push(current);
  return cells;
}

function mdIsTable(lines, index) {
  if (index + 1 >= lines.length) return false;
  if (lines[index].indexOf('|') === -1) return false;
  const delimiter = mdCells(lines[index + 1]);
  if (delimiter.length < 1) return false;
  return delimiter.every(function (cell) {
    return /^\s*:?-{3,}:?\s*$/.test(cell);
  });
}

function mdTable(lines, start) {
  const head = mdCells(lines[start]);
  const align = mdCells(lines[start + 1]).map(function (cell) {
    const value = cell.trim();
    if (/^:-+:$/.test(value)) return 'center';
    if (/^-+:$/.test(value)) return 'right';
    return 'left';
  });
  const rows = [];
  let index = start + 2;
  while (index < lines.length && lines[index].trim() && lines[index].indexOf('|') !== -1) {
    rows.push(mdCells(lines[index]));
    index += 1;
  }
  function cell(tag, value, position) {
    const kind = align[position] || 'left';
    const cls = kind === 'left' ? '' : ' class="align-' + kind + '"';
    return '<' + tag + cls + '>' + mdInline(String(value).trim()) + '</' + tag + '>';
  }
  const headHtml = '<thead><tr>' + head.map(function (value, position) {
    return cell('th', value, position);
  }).join('') + '</tr></thead>';
  const bodyHtml = rows.map(function (row) {
    return '<tr>' + head.map(function (unused, position) {
      return cell('td', row[position] == null ? '' : row[position], position);
    }).join('') + '</tr>';
  }).join('');
  return {
    html: '<div class="md-table"><table>' + headHtml + '<tbody>' + bodyHtml + '</tbody></table></div>',
    next: index
  };
}

function mdList(lines, start) {
  const first = mdItem(lines[start]);
  const base = first.indent;
  const tag = first.ordered ? 'ol' : 'ul';
  const entries = [];
  let index = start;
  while (index < lines.length) {
    const item = mdItem(lines[index]);
    if (!item || item.indent < base) break;
    if (item.indent > base) break;
    if ((item.ordered ? 'ol' : 'ul') !== tag) break;
    let body = item.text;
    let next = index + 1;
    while (next < lines.length && lines[next].trim()) {
      if (mdItem(lines[next])) break;
      if (mdIndent(lines[next]) <= base) break;
      body += ' ' + lines[next].trim();
      next += 1;
    }
    const entry = { text: body, children: '' };
    if (next < lines.length) {
      const nested = mdItem(lines[next]);
      if (nested && nested.indent > base) {
        const child = mdList(lines, next);
        entry.children = child.html;
        next = child.next;
      }
    }
    entries.push(entry);
    index = next;
  }
  const html = '<' + tag + '>' + entries.map(function (entry) {
    const task = entry.text.match(/^\[( |x|X)\]\s+(.*)$/);
    const box = task
      ? '<input type="checkbox" disabled' + (task[1] === ' ' ? '' : ' checked') +
        ' aria-label="' + (task[1] === ' ' ? 'not done' : 'done') + '"> '
      : '';
    const body = task ? task[2] : entry.text;
    return '<li' + (task ? ' class="task"' : '') + '>' + box + mdInline(body) +
      entry.children + '</li>';
  }).join('') + '</' + tag + '>';
  return { html: html, next: index };
}

function renderMarkdown(source) {
  const text = esc(String(source == null ? '' : source)).replace(/\r\n?/g, '\n');
  const lines = text.split('\n');
  const blocks = [];
  let paragraph = [];
  let index = 0;

  function flushParagraph() {
    if (!paragraph.length) return;
    blocks.push('<p>' + paragraph.map(mdInline).join('<br>') + '</p>');
    paragraph = [];
  }

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      flushParagraph();
      index += 1;
      continue;
    }
    const fence = line.match(/^\s*```\s*([\w+-]*)\s*$/);
    if (fence) {
      flushParagraph();
      const code = [];
      index += 1;
      while (index < lines.length && !/^\s*```/.test(lines[index])) {
        code.push(lines[index]);
        index += 1;
      }
      index += 1;
      blocks.push('<pre><code>' + code.join('\n') + '</code></pre>');
      continue;
    }
    if (mdIsTable(lines, index)) {
      flushParagraph();
      const table = mdTable(lines, index);
      blocks.push(table.html);
      index = table.next;
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      flushParagraph();
      const level = heading[1].length;
      blocks.push('<h' + level + '>' + mdInline(heading[2]) + '</h' + level + '>');
      index += 1;
      continue;
    }
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) {
      flushParagraph();
      blocks.push('<hr>');
      index += 1;
      continue;
    }
    if (/^\s*>\s?/.test(line)) {
      flushParagraph();
      const quote = [];
      while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
        quote.push(lines[index].replace(/^\s*>\s?/, ''));
        index += 1;
      }
      blocks.push('<blockquote>' + quote.map(mdInline).join('<br>') + '</blockquote>');
      continue;
    }
    if (mdItem(line)) {
      flushParagraph();
      const list = mdList(lines, index);
      blocks.push(list.html);
      index = list.next;
      continue;
    }
    paragraph.push(line);
    index += 1;
  }
  flushParagraph();
  return blocks.join('');
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
    (turn.reply
      ? '<div class="reply md" data-stage="reply"><strong>byo ›</strong> ' +
        renderMarkdown(turn.reply) + '</div>'
      : '') +
    receipt +
    '</article>';
}

// The live card separates the three things a turn actually does — thinking, tool
// calls and output — into their own lanes. Each lane names the map component it
// stands for (data-node) so the lit component and the running lane agree.
// The persisted trace of one turn: the memory decision, each model round with the
// text it produced, and each tool call. Loaded on demand from /api/turn so the
// history stays cheap until a person opens it.
function formatMs(value) {
  const ms = Number(value) || 0;
  if (ms >= 1000) return (ms / 1000).toFixed(1).replace(/\.0$/, '') + ' s';
  return ms + ' ms';
}

function traceStep(kind, tag, head, meta, body) {
  return '<div class="trace-step" data-kind="' + kind + '">' +
    '<div class="trace-tag">' + tag + '</div>' +
    '<div class="trace-main"><div class="trace-head">' + head +
    (meta ? ' <span class="trace-meta">' + meta + '</span>' : '') + '</div>' +
    body + '</div></div>';
}

// The persisted trace of one turn: the memory decision, each model round with the
// text it produced, and each tool call. Loaded on demand from /api/turn so the
// history stays cheap until a person opens it.
function traceHtml(payload) {
  const turn = (payload && payload.turn) || {};
  const steps = turn.steps || [];
  const reply = String(turn.reply == null ? '' : turn.reply).trim();
  const parts = [];
  steps.forEach(function (step) {
    if (step.kind === 'gate') {
      parts.push(traceStep(
        'gate', 'gate', esc(step.decision || '?'), '',
        step.reason ? '<div class="trace-text">' + esc(step.reason) + '</div>' : ''
      ));
    } else if (step.kind === 'llm') {
      const text = String(step.text == null ? '' : step.text).trim();
      const answer = !text || text === reply;
      const meta = esc(step.model || '') + ' · ' + esc(formatMs(step.duration_ms)) +
        ' · ' + esc(step.in || 0) + ' in / ' + esc(step.out || 0) + ' out';
      const body = !answer && text ? '<div class="trace-text">' + esc(text) + '</div>' : '';
      parts.push(traceStep(
        'llm', answer ? 'answer' : 'think',
        'round ' + esc(step.iteration == null ? '?' : step.iteration), meta, body
      ));
    } else if (step.kind === 'tool') {
      const failed = step.ok === false;
      const meta = esc(formatMs(step.duration_ms)) + (failed ? ' · failed' : ' · ok');
      const args = String(step.args == null ? '' : step.args);
      const hint = esc(args.length > 80 ? args.slice(0, 79) + '…' : args);
      // Every tool call folds on its own inside the turn's trace.
      const details = '<details class="trace-tool"' + (failed ? ' data-failed="true"' : '') + '>' +
        '<summary><span class="trace-mark" aria-hidden="true"></span>' +
        '<span class="trace-tool-name">' + esc(step.tool || '?') + '</span>' +
        '<span class="trace-tool-hint">' + hint + '</span>' +
        '<span class="trace-meta">' + meta + '</span></summary>' +
        '<div class="trace-tool-body">' +
        '<div class="trace-code"><span class="trace-code-label">in</span>' + esc(args) + '</div>' +
        '<div class="trace-code"><span class="trace-code-label">out</span>' +
        esc(step.output || '') + '</div></div></details>';
      parts.push('<div class="trace-step" data-kind="tool">' +
        '<div class="trace-tag">tool</div>' +
        '<div class="trace-main">' + details + '</div></div>');
    } else if (step.kind === 'error') {
      parts.push(traceStep(
        'error', 'error', esc(step.stage || '?'), '',
        '<div class="trace-text">' + esc(step.message || '') + '</div>'
      ));
    }
  });
  if (!parts.length) return '<p class="empty">This turn recorded no steps.</p>';
  return parts.join('');
}

function liveLane(item) {
  const open = item.live ? 'true' : 'false';
  const prose = item.type === 'output' || item.type === 'streaming';
  const body = item.body
    ? '<div class="lane-body' + (prose ? ' md' : '') + '">' +
      (prose ? renderMarkdown(item.body) : esc(item.body)) +
      (prose && item.live ? '<span class="caret" aria-hidden="true"></span>' : '') +
      '</div>'
    : item.pending
      ? '<div class="lane-body pending">' + esc(item.pending) + '</div>'
      : '';
  return '<section class="lane lane-' + esc(item.type) + '" data-node="' + esc(item.node || '') +
    '" data-open="' + open + '" data-state="' + (item.live ? 'live' : 'done') + '">' +
    '<div class="lane-head"><span class="lane-title">' + esc(item.title) + '</span>' +
    (item.meta ? '<span class="lane-meta">' + esc(item.meta) + '</span>' : '') + '</div>' +
    body + '</section>';
}

function liveCard(live) {
  const lanes = (live.items || []).map(liveLane).join('');
  const receipt = live.receipt ? '<div class="receipt">' + receiptLine(live.receipt) + '</div>' : '';
  let state = '';
  if (live.state === 'failed') {
    state = ' <span class="chip bad" data-state="failed">failed</span>';
  } else if (live.state === 'limited') {
    state = ' <span class="chip" data-state="limited">step limit</span>';
  }
  return '<article class="card live-card">' +
    '<div class="meta"><span>live</span><span>' + esc(live.source || 'dashboard') + '</span>' + state + '</div>' +
    '<div class="reply"><strong>you ›</strong> ' + esc(live.user_message) + '</div>' +
    lanes + receipt +
    '</article>';
}

function focusCard(turn) {
  return '<div id="live">' + turnCard(turn) + '</div>';
}