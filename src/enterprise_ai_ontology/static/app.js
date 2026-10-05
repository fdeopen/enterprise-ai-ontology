/* No remote libraries, executable definitions, or HTML interpolation of user input. */
(() => {
  'use strict';
  const boot = window.ONTOLOGY_BOOTSTRAP;
  const $ = id => document.getElementById(id);
  const NS = 'http://www.w3.org/2000/svg';
  const kinds = {entities: ['Entity', '实体', 'entity'], relationships: ['Relationship', '关系', 'relationship'], actions: ['Action', '动作', 'action'], rules: ['Rule', '规则', 'rule'], events: ['Event', '事件', 'event']};
  const colors = {entities: '#176650', actions: '#b97935', rules: '#8570a4', events: '#557a99'};
  const industries = [['ecommerce', '电商', '01'], ['foreign_trade', '外贸', '02'], ['manufacturing', '制造', '03'], ['medical_aesthetics', '医美', '04'], ['recruitment', '招聘', '05']];
  let model = boot.ontology, yaml = boot.yaml, view = 'entities', selected = null, focus = null;
  let editorDirty = false, loadSeq = 0, toastTimer, bounds, baseBounds, drag;
  const offline = boot.mode === 'offline';
  function el(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }
  function sv(tag, attributes = {}, text) { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attributes)) n.setAttribute(k, v); if (text !== undefined) n.textContent = text; return n; }
  function toast(text) { $('toast').textContent = text; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('toast').hidden = true; }, 5000); }
  function find(kind, id) { return (model[kind] || []).find(item => item.id === id); }
  function items() { return Object.entries(kinds).flatMap(([kind]) => model[kind].map(object => ({kind, object}))); }
  function matches(object) { const q = $('search').value.trim().toLowerCase(); return !q || (object.id + ' ' + object.label + ' ' + object.description).toLowerCase().includes(q); }
  function chip(kind, id) { const object = find(kind, id); const b = el('button', 'link-chip', object ? object.label : id); b.addEventListener('click', () => select(kind, id)); return b; }
  function group(parent, title, nodes) { if (!nodes.length) return; const h = el('div', 'detail-heading', title); h.append(el('span', '', String(nodes.length).padStart(2, '0'))); parent.append(h, ...nodes); }
  function setResult(id, text, error = false) { $(id).textContent = text; $(id).classList.toggle('error', error); }
  async function api(path, data) {
    const options = data === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)};
    const response = await fetch(path, options);
    const result = response.headers.get('content-type')?.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) throw new Error(result.error || '请求失败');
    return result;
  }
  function draftGuard() { if (!editorDirty) return true; toast('编辑器有未应用的草稿，请先“校验并应用”或“恢复当前定义”。'); activate('editor'); return false; }
  function loadModel(data) {
    model = data.ontology; yaml = data.yaml; focus = null; selected = null; editorDirty = false;
    $('search').value = ''; $('kind-filter').value = 'all';
    $('model-name').textContent = model.name; document.title = model.name + ' · Ontology';
    $('model-version').textContent = 'v' + model.version; $('model-description').textContent = model.description;
    const counts = [['entities', '实体'], ['properties', '属性'], ['relationships', '关系'], ['actions', '动作'], ['rules', '规则'], ['events', '事件']];
    $('stats').replaceChildren(...counts.map(([key, label]) => { const n = el('div', 'stat'); n.append(el('strong', '', String(key === 'properties' ? model.entities.reduce((s, e) => s + e.properties.length, 0) : model[key].length).padStart(2, '0')), el('span', '', label)); return n; }));
    document.querySelector('[data-view="scenarios"] span').textContent = String(model.ai_scenarios.length).padStart(2, '0');
    $('record-entity').replaceChildren(...model.entities.map(e => { const o = el('option', '', e.label); o.value = e.id; return o; }));
    renderIndustries(); renderList(); renderScenarios(); resetEditor(); seedRecord();
    const center = [...model.entities].sort((a, b) => degree(b.id) - degree(a.id))[0];
    selected = {kind: 'entities', id: center.id};
    activate('entities'); renderInspector(); renderList();
  }
  function renderIndustries() {
    $('industry-list').replaceChildren(...industries.map(([id, label, index]) => {
      const b = el('button', 'industry-button' + (model.id === id ? ' active' : '')); b.dataset.industry = id;
      b.append(el('span', 'industry-icon', index), el('span', '', label), el('span', 'arrow', '↗'));
      b.setAttribute('aria-pressed', String(model.id === id));
      if (offline) { b.disabled = model.id !== id; b.title = '离线报告仅包含当前模型'; }
      b.addEventListener('click', async () => {
        if (offline || !draftGuard()) return;
        const seq = ++loadSeq; b.disabled = true;
        try { const data = await api('/api/examples/' + id); if (seq === loadSeq) { loadModel(data); toast('已加载' + label + '行业示例'); } }
        catch (err) { toast(err.message); } finally { b.disabled = false; }
      }); return b;
    }));
  }
  function renderList() {
    const filtered = items().filter(({kind, object}) => ($('kind-filter').value === 'all' || $('kind-filter').value === kind) && matches(object));
    $('object-count').textContent = String(filtered.length).padStart(2, '0');
    $('object-list').replaceChildren(...filtered.map(({kind, object}) => {
      const b = el('button', 'object-button' + (selected?.kind === kind && selected?.id === object.id ? ' active' : ''));
      const label = el('span', '', object.label); label.append(el('small', '', object.id));
      b.append(el('i', 'dot ' + kinds[kind][2]), label); b.addEventListener('click', () => select(kind, object.id)); return b;
    }));
    if (!filtered.length) $('object-list').append(el('p', 'no-results', '没有匹配的对象'));
  }
  function select(kind, id) { selected = {kind, id}; renderList(); renderInspector(); if (view === 'entities' || view === 'full') drawGraph(false); }
  function propertyCard(p, primary) {
    const card = el('div', 'property-card'), top = el('div', 'property-top'); top.append(el('b', '', p.id), el('small', '', p.type));
    card.append(top, el('p', '', p.label + (p.unit ? ' · ' + p.unit : '')));
    const flags = el('div', 'property-flags');
    for (const flag of [primary ? '⌑ 主键' : '', p.required ? '必填' : '可选', p.nullable ? '可为空' : '', p.sensitive ? '敏感字段' : '']) if (flag) flags.append(el('span', '', flag));
    card.append(flags); if (p.enum_values.length) card.append(el('p', '', p.enum_values.join(' / '))); card.title = p.description; return card;
  }
  function renderInspector() {
    const root = $('inspector'); root.replaceChildren(); if (!selected) return;
    const {kind, id} = selected, object = find(kind, id); if (!object) return;
    root.append(el('div', 'eyebrow', 'OBJECT INSPECTOR'));
    const pill = el('div', 'type-pill'); pill.append(el('i', 'dot ' + kinds[kind][2]), document.createTextNode(kinds[kind][0].toUpperCase()));
    root.append(pill, el('h2', '', object.label), el('div', 'object-id', object.id), el('p', 'description', object.description));
    if (object.human_approval !== undefined) root.append(el('div', 'approval', object.human_approval ? '◎ 需要人工审批 · 模型只提供建议' : '○ 未声明人工审批 · 本工具不执行动作'));
    if (object.properties) group(root, '属性 · PROPERTIES', object.properties.map(p => propertyCard(p, p.id === object.primary_key)));
    if (object.parameters) group(root, '输入参数 · PARAMETERS', object.parameters.map(p => propertyCard(p, false)));
    if (object.payload) group(root, '事件载荷 · PAYLOAD', object.payload.map(p => propertyCard(p, false)));
    if (object.entity) group(root, '关联实体', [chip('entities', object.entity)]);
    if (kind === 'relationships') { group(root, '关系两端', [chip('entities', object.source), el('p', 'description', object.cardinality.replaceAll('_', ' ')), chip('entities', object.target)]); }
    if (kind === 'entities') {
      group(root, '关系 · RELATIONSHIPS', model.relationships.filter(r => r.source === id || r.target === id).map(r => chip('relationships', r.id)));
      for (const groupName of ['actions', 'rules', 'events']) group(root, kinds[groupName][1], model[groupName].filter(o => o.entity === id).map(o => chip(groupName, o.id)));
    }
    if (object.requires_rules) group(root, '执行前须通过', object.requires_rules.map(id => chip('rules', id)));
    if (object.emits) group(root, '触发事件', object.emits.map(id => chip('events', id)));
    if (object.conditions) {
      group(root, '条件断言 · ' + object.match.toUpperCase(), object.conditions.map(c => el('pre', 'condition-code', c.property + ' ' + c.operator + (['exists', 'absent'].includes(c.operator) ? '' : ' ' + JSON.stringify(c.value)))));
      root.append(el('p', 'description', object.severity.toUpperCase() + ' · ' + object.message));
    }
    const scenarios = model.ai_scenarios.filter(s => (s[kind] || []).includes(id));
    group(root, '应用于 AI 场景', scenarios.map(s => { const b = el('button', 'link-chip', s.label); b.addEventListener('click', () => { activate('scenarios'); $('scenario-' + s.id)?.scrollIntoView({block: 'nearest', behavior: 'smooth'}); }); return b; }));
  }
  function degree(id) { return model.relationships.filter(r => r.source === id || r.target === id).length; }
  function graphData() {
    if (view === 'entities') {
      const ordered = [...model.entities].sort((a, b) => degree(b.id) - degree(a.id)), count = ordered.length;
      const radius = Math.max(270, count * 29), width = radius * 2 + 290, height = radius * 2 + 180, cx = width / 2, cy = height / 2;
      const nodes = ordered.map((o, i) => {
        const angle = -Math.PI / 2 + (i - 1) * 2 * Math.PI / Math.max(count - 1, 1);
        return {kind: 'entities', object: o, key: 'entities:' + o.id, x: i === 0 ? cx : cx + radius * Math.cos(angle), y: i === 0 ? cy : cy + radius * Math.sin(angle)};
      });
      return {width, height, nodes, edges: model.relationships.map(r => ({from: 'entities:' + r.source, to: 'entities:' + r.target, label: r.label, relation: r.id, cardinality: r.cardinality}))};
    }
    const groups = ['actions', 'entities', 'rules', 'events'];
    const max = Math.max(...groups.map(k => model[k].length), 1), height = Math.max(660, max * 128 + 100), width = 1300;
    const nodes = groups.flatMap((kind, col) => model[kind].map((object, i) => ({kind, object, key: kind + ':' + object.id, x: 170 + col * 320, y: 100 + i * (height - 200) / Math.max(model[kind].length - 1, 1)})));
    const edges = model.relationships.map(r => ({from: 'entities:' + r.source, to: 'entities:' + r.target, label: r.label, relation: r.id, cardinality: r.cardinality}));
    for (const kind of ['actions', 'rules', 'events']) for (const o of model[kind]) edges.push({from: 'entities:' + o.entity, to: kind + ':' + o.id, label: '', support: true, meaning: {actions: '拥有动作', rules: '声明规则', events: '关联事件'}[kind]});
    for (const a of model.actions) { for (const id of a.emits) edges.push({from: 'actions:' + a.id, to: 'events:' + id, label: '', support: true, meaning: '触发事件'}); for (const id of a.requires_rules) edges.push({from: 'rules:' + id, to: 'actions:' + a.id, label: '', support: true, meaning: '动作前置断言'}); }
    return {width, height, nodes, edges};
  }
  function setBounds() { $('graph').setAttribute('viewBox', `${bounds.x} ${bounds.y} ${bounds.w} ${bounds.h}`); }
  function drawGraph(reset = true) {
    const graph = $('graph'), data = graphData(), {nodes, edges} = data;
    graph.replaceChildren();
    if (reset || !bounds) { baseBounds = {x: 0, y: 0, w: data.width, h: data.height}; bounds = {...baseBounds}; }
    setBounds();
    const defs = sv('defs'), marker = sv('marker', {id: 'arrow', markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: 'auto', markerUnits: 'userSpaceOnUse'}); marker.append(sv('path', {d: 'M0,0 L8,4 L0,8', fill: '#9eb8a8'})); defs.append(marker); graph.append(defs);
    const indexes = new Map(nodes.map(n => [n.key, n]));
    const visible = node => matches(node.object) && (!focus || (focus[node.kind] || []).includes(node.object.id));
    const edgeLayer = sv('g'), labelLayer = sv('g'); graph.append(edgeLayer, labelLayer);
    edges.forEach((edge, index) => {
      const a = indexes.get(edge.from), b = indexes.get(edge.to); if (!a || !b) return;
      const dx = b.x - a.x, dy = b.y - a.y;
      let path, mx, my;
      if (a === b) { path = `M${a.x-50},${a.y-44} C${a.x-120},${a.y-135} ${a.x+120},${a.y-135} ${a.x+50},${a.y-44}`; mx = a.x; my = a.y - 100; }
      else if (view === 'full' && a.x === b.x) { const bend = 125 + (index % 3) * 26; path = `M${a.x+90},${a.y} C${a.x+bend},${a.y} ${b.x+bend},${b.y} ${b.x+90},${b.y}`; mx = a.x + bend; my = (a.y + b.y) / 2; }
      else {
        const scale = Math.max(Math.abs(dx) / 92, Math.abs(dy) / 47), sx = a.x + dx / scale, sy = a.y + dy / scale, tx = b.x - dx / scale, ty = b.y - dy / scale;
        const bend = view === 'full' ? (index % 3 - 1) * 22 : 0;
        const cx = (sx + tx) / 2 - dy * .05 + bend, cy = (sy + ty) / 2 + dx * .05;
        path = `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`; mx = (sx + 2 * cx + tx) / 4; my = (sy + 2 * cy + ty) / 4 - 7;
      }
      const g = sv('g', {class: visible(a) && visible(b) ? '' : 'edge-dimmed'});
      const line = sv('path', {d: path, class: 'edge-line' + (edge.support ? ' support' : ''), 'marker-end': 'url(#arrow)'}); g.append(line);
      if (edge.meaning) line.append(sv('title', {}, a.object.label + ' → ' + b.object.label + ' · ' + edge.meaning));
      const label = sv('text', {x: mx, y: my, 'text-anchor': 'middle', class: 'edge-label'}, edge.label);
      if (edge.relation) { const title = sv('title', {}, edge.label + ' · ' + edge.cardinality); line.append(title); line.style.cursor = 'pointer'; line.addEventListener('click', () => select('relationships', edge.relation)); label.style.cursor = 'pointer'; label.addEventListener('click', () => select('relationships', edge.relation)); }
      edgeLayer.append(g); if (view === 'entities') { if (!visible(a) || !visible(b)) label.classList.add('edge-dimmed'); labelLayer.append(label); }
    });
    for (const node of nodes) {
      const {kind, object, x, y} = node;
      const g = sv('g', {class: 'node' + (selected?.kind === kind && selected?.id === object.id ? ' selected' : '') + (!visible(node) ? ' node-dimmed' : ''), transform: `translate(${x-90} ${y-44})`, tabindex: 0, role: 'button', 'aria-label': kinds[kind][1] + '：' + object.label});
      g.append(sv('rect', {width: 180, height: 88, rx: 9, class: 'body'}), sv('rect', {x: 13, y: 16, width: 5, height: 16, rx: 2, fill: colors[kind]}), sv('text', {x: 26, y: 30, class: 'node-label'}, object.label.length > 9 ? object.label.slice(0, 8) + '…' : object.label), sv('text', {x: 14, y: 50, class: 'node-id'}, object.id.length > 23 ? object.id.slice(0, 21) + '…' : object.id), sv('text', {x: 14, y: 73, class: 'node-meta'}, kind === 'entities' ? `${object.properties.length} 个属性 · ${degree(object.id)} 条关系` : kinds[kind][0] + (object.human_approval ? ' · 人工审批' : '')));
      g.append(sv('title', {}, object.label + ' · ' + object.description));
      g.addEventListener('click', () => select(kind, object.id)); g.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(kind, object.id); } }); graph.append(g);
    }
    $('graph-empty').hidden = nodes.some(visible);
  }
  function activate(next) {
    view = next;
    document.querySelectorAll('[data-view]').forEach(b => { b.classList.toggle('active', b.dataset.view === view); b.setAttribute('aria-pressed', String(b.dataset.view === view)); });
    for (const key of ['graph', 'scenarios', 'editor', 'check']) $(key + '-view').hidden = key === 'graph' ? !['entities', 'full'].includes(view) : view !== key;
    $('clear-focus').hidden = !focus || !['entities', 'full'].includes(view);
    $('view-description').textContent = focus && ['entities', 'full'].includes(view) ? '场景聚焦：' + focus.label : ({entities: '点击对象查看定义与业务语义', full: '实体、动作、规则、事件的完整关联', scenarios: '可追溯的 AI 应用场景', editor: '先校验，再更新图谱', check: '验证单条记录，不执行业务动作'})[view];
    if (['entities', 'full'].includes(view)) drawGraph();
    if (view === 'editor' && !editorDirty) resetEditor();
  }
  function renderScenarios() {
    $('scenario-list').replaceChildren(...model.ai_scenarios.map((scenario, index) => {
      const card = el('article', 'scenario-card'); card.id = 'scenario-' + scenario.id;
      const top = el('div', 'scenario-top'), heading = el('div'); heading.append(el('h3', '', scenario.label), el('p', '', scenario.task)); top.append(el('span', 'scenario-number', String(index + 1).padStart(2, '0')), heading); card.append(top);
      const links = el('div'); for (const id of scenario.entities) links.append(chip('entities', id)); card.append(links);
      const grid = el('div', 'scenario-grid');
      for (const [key, label] of [['inputs', 'INPUT / 输入'], ['outputs', 'OUTPUT / 输出'], ['success_metrics', 'EVALUATION / 评估指标']]) { const cell = el('div'), list = el('ul'); list.append(...scenario[key].map(t => el('li', '', t))); cell.append(el('h4', '', label), list); grid.append(cell); }
      card.append(grid, el('div', 'oversight', '◎ 人工审核：' + scenario.human_oversight));
      const button = el('button', 'button subtle', '在业务图中查看关联 ↗'); button.addEventListener('click', () => { focus = scenario; activate('full'); }); card.append(button); return card;
    }));
    if (!model.ai_scenarios.length) $('scenario-list').append(el('p', 'no-results', '当前定义未配置 AI 场景。'));
  }
  function resetEditor() { $('definition-editor').value = $('editor-format').value === 'json' ? JSON.stringify(model, null, 2) : yaml; editorDirty = false; $('valid-status').textContent = '✓ 定义已校验'; setResult('editor-result', offline ? '离线浏览模式。使用本地工作台或 CLI 校验修改。' : '当前定义已通过结构与引用校验。'); }
  function seedRecord() {
    const entity = find('entities', $('record-entity').value); if (!entity) return;
    const record = {};
    for (const p of entity.properties) {
      if (!p.required) continue;
      record[p.id] = ({string: p.id === entity.primary_key ? 'DEMO-001' : '示例值', integer: 1, number: 1, boolean: false, date: '2026-01-01', datetime: '2026-01-01T09:00:00+08:00', enum: p.enum_values[0], string_list: [], json: {}})[p.type];
    }
    for (const rule of model.rules.filter(r => r.entity === entity.id)) for (const c of rule.conditions) {
      if (c.operator === 'eq') record[c.property] = c.value;
      else if (c.operator === 'in') record[c.property] = c.value[0];
      else if (['gte', 'lte'].includes(c.operator)) record[c.property] = c.value;
      else if (['gt', 'lt'].includes(c.operator) && typeof c.value === 'number') record[c.property] = c.value + (c.operator === 'gt' ? 1 : -1);
    }
    $('record-editor').value = JSON.stringify(record, null, 2);
    setResult('record-result', offline ? '离线 HTML 提供图谱浏览；记录校验请使用 CLI 或本地工作台。' : '生成值用于试验；运行检查后才显示校验结论。');
  }
  function download(content, name, type) { const url = URL.createObjectURL(new Blob([content], {type})); const a = el('a'); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
  document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => activate(b.dataset.view)));
  $('search').addEventListener('input', () => { renderList(); if (['entities', 'full'].includes(view)) drawGraph(false); });
  $('kind-filter').addEventListener('change', renderList);
  $('clear-focus').addEventListener('click', () => { focus = null; activate(view); });
  $('definition-editor').addEventListener('input', () => { editorDirty = true; $('valid-status').textContent = '草稿未校验'; setResult('editor-result', '草稿已修改，尚未应用到图谱。'); });
  let previousFormat = 'yaml';
  $('editor-format').addEventListener('change', () => { if (editorDirty) { $('editor-format').value = previousFormat; toast('请先应用或恢复当前草稿，再切换格式。'); } else { previousFormat = $('editor-format').value; resetEditor(); } });
  $('reset-editor').addEventListener('click', resetEditor);
  $('apply-editor').addEventListener('click', async () => {
    const button = $('apply-editor'); button.disabled = true;
    const text = $('definition-editor').value, format = $('editor-format').value;
    try { const data = await api('/api/validate', {text, format}); if ($('definition-editor').value !== text) throw new Error('校验期间草稿已变化，请重新校验。'); loadModel(data); activate('editor'); setResult('editor-result', '✓ 定义有效。结构、引用和规则类型检查均通过，图谱已更新。'); toast('定义已应用，请导出保存。'); }
    catch (err) { setResult('editor-result', err.message, true); } finally { button.disabled = false; }
  });
  $('record-entity').addEventListener('change', seedRecord);
  $('record-editor').addEventListener('input', () => setResult('record-result', '记录已修改，请重新检查。'));
  $('check-record').addEventListener('click', async () => {
    const button = $('check-record'); button.disabled = true;
    try {
      const result = await api('/api/check', {text: JSON.stringify(model), format: 'json', entity: $('record-entity').value, record_text: $('record-editor').value});
      const lines = [(result.valid ? '✓ 记录通过' : '✕ 记录未通过'), ...result.errors, ...result.rules.map(r => `${r.passed ? '✓' : '✕'} [${r.severity}] ${r.label}：${r.message}`)];
      if (!result.rules.length && !result.errors.length) lines.push('当前实体未定义业务规则；字段类型检查通过。');
      setResult('record-result', lines.join('\n'), !result.valid);
    } catch (err) { setResult('record-result', err.message, true); } finally { button.disabled = false; }
  });
  $('import-button').addEventListener('click', () => { if (draftGuard()) $('file-input').click(); });
  $('file-input').addEventListener('change', async () => {
    const file = $('file-input').files[0]; if (!file) return;
    const seq = ++loadSeq;
    try { if (file.size > 2 * 1024 * 1024) throw new Error('文件不能超过 2 MiB'); const format = file.name.toLowerCase().endsWith('.json') ? 'json' : 'yaml'; const data = await api('/api/validate', {text: await file.text(), format}); if (seq === loadSeq) { loadModel(data); toast('导入成功：' + file.name); } }
    catch (err) { toast('导入失败：' + err.message); } finally { $('file-input').value = ''; }
  });
  $('export-button').addEventListener('click', async () => {
    const button = $('export-button'), format = $('export-format').value; button.disabled = true;
    try {
      let content;
      if (format === 'html') content = await api('/api/render', {text: JSON.stringify(model), format: 'json'});
      else content = format === 'json' ? JSON.stringify(model, null, 2) + '\n' : yaml;
      download(content, model.id + '.' + format, format === 'html' ? 'text/html' : 'text/plain'); toast(editorDirty ? '已导出通过校验的版本；未应用草稿不包含在内。' : '已导出 ' + format.toUpperCase());
    } catch (err) { toast(err.message); } finally { button.disabled = false; }
  });
  function zoom(factor) { const next = bounds.w * factor; if (next < baseBounds.w * .3 || next > baseBounds.w * 4) return; bounds.x += (bounds.w - next) / 2; bounds.y += (bounds.h - bounds.h * factor) / 2; bounds.w = next; bounds.h *= factor; setBounds(); }
  $('zoom-in').addEventListener('click', () => zoom(.8)); $('zoom-out').addEventListener('click', () => zoom(1.25)); $('zoom-reset').addEventListener('click', () => { bounds = {...baseBounds}; setBounds(); });
  $('graph').addEventListener('wheel', event => { event.preventDefault(); zoom(event.deltaY > 0 ? 1.08 : .92); }, {passive: false});
  $('graph').addEventListener('pointerdown', event => { if (event.target.closest('.node') || event.button !== 0) return; drag = {x: event.clientX, y: event.clientY, bounds: {...bounds}}; $('graph').setPointerCapture(event.pointerId); $('graph').classList.add('dragging'); });
  $('graph').addEventListener('pointermove', event => { if (!drag) return; const rect = $('graph').getBoundingClientRect(), scale = Math.max(drag.bounds.w / rect.width, drag.bounds.h / rect.height); bounds.x = drag.bounds.x - (event.clientX - drag.x) * scale; bounds.y = drag.bounds.y - (event.clientY - drag.y) * scale; setBounds(); });
  for (const name of ['pointerup', 'pointercancel']) $('graph').addEventListener(name, () => { drag = null; $('graph').classList.remove('dragging'); });
  if (offline) {
    $('mode-badge').textContent = '● OFFLINE SNAPSHOT'; $('import-button').hidden = true;
    $('export-format').querySelector('[value="html"]').remove();
    $('apply-editor').hidden = true; $('check-record').hidden = true; $('definition-editor').readOnly = true; $('record-editor').readOnly = true;
    $('footer-note').textContent = '独立 HTML · 离线快照 · JSON / YAML 可导出';
  }
  loadModel(boot);
})();
