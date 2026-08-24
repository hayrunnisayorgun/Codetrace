import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables: {
    darkMode: true,
    background: 'transparent',
    fontFamily: 'ui-monospace, SFMono-Regular, monospace',
    fontSize: '11px',
    primaryColor: '#161c2e',
    primaryTextColor: '#e2e8f0',
    primaryBorderColor: '#38bdf8',
    secondaryColor: '#1c2438',
    tertiaryColor: '#111625',
    lineColor: '#64748b',
    clusterBkg: '#0e121f',
    clusterBorder: '#1c2438',
    edgeLabelBackground: '#111625',
    nodeTextColor: '#e2e8f0',
    mainBkg: '#161c2e',
    titleColor: '#e2e8f0'
  },
  flowchart: {
    curve: 'basis',
    htmlLabels: true,
    nodeSpacing: 35,
    rankSpacing: 70
  },
  securityLevel: 'loose',
});

// 🗺️ Builds the architecture diagram from the raw dependency graph.
//
// Collapsed layers render as a single box and every import crossing them is
// merged into one labelled arrow -- that is what keeps the default view clean
// instead of drawing all ~40 file-to-file arrows at once. Expanding a layer
// swaps its box for the individual files, so detail is opt-in per layer.
function buildMermaidFromGraph(graph, expandedNodes) {
  if (!graph?.layers?.length) return '';

  const layerOfFile = {};
  const fileNodeId = {};
  const layerNodeId = {};

  graph.layers.forEach((layer, li) => {
    layerNodeId[layer.name] = `L${li}`;
    layer.files.forEach((file, fi) => {
      layerOfFile[file] = layer.name;
      fileNodeId[file] = `F${li}_${fi}`;
    });
  });

  const lines = [
    "%%{init: {'flowchart': {'curve': 'basis', 'nodeSpacing': 28, 'rankSpacing': 50, 'padding': 8, 'htmlLabels': true}}}%%",
    'flowchart TB'
  ];

  graph.layers.forEach((layer) => {
    const id = layerNodeId[layer.name];
    if (expandedNodes[layer.name]) {
      lines.push(`  subgraph ${id}_group["${layer.name}"]`);
      lines.push('    direction LR');
      layer.files.forEach((file) => {
        lines.push(`    ${fileNodeId[file]}("📄 ${file.split('/').pop()}")`);
      });
      lines.push('  end');
    } else {
      const count = layer.files.length;
      lines.push(`  ${id}("<b>${layer.name}</b><br/>${count} file${count === 1 ? '' : 's'}")`);
    }
  });

  // Point every import at whichever node currently represents its endpoint and
  // tally how many imports each pair of boxes stands for.
  const pairCounts = new Map();
  (graph.file_edges || []).forEach(({ source, target }) => {
    const sourceLayer = layerOfFile[source];
    const targetLayer = layerOfFile[target];
    if (!sourceLayer || !targetLayer) return;

    const from = expandedNodes[sourceLayer] ? fileNodeId[source] : layerNodeId[sourceLayer];
    const to = expandedNodes[targetLayer] ? fileNodeId[target] : layerNodeId[targetLayer];
    if (from === to) return;

    const key = `${from}|${to}`;
    pairCounts.set(key, (pairCounts.get(key) || 0) + 1);
  });

  // Drawing every dependency turns the chart into unreadable spaghetti, and the
  // long tail of one-off imports is not what anyone reads a diagram for. Each
  // box therefore keeps exactly one arrow -- its heaviest dependency -- labelled
  // with how many imports that arrow stands for.
  const strongestPerSource = new Map();
  pairCounts.forEach((count, key) => {
    const from = key.split('|')[0];
    const current = strongestPerSource.get(from);
    if (!current || count > current.count) {
      strongestPerSource.set(from, { key, count });
    }
  });

  strongestPerSource.forEach(({ key, count }) => {
    const [from, to] = key.split('|');
    lines.push(count > 1 ? `  ${from} -->|${count}| ${to}` : `  ${from} --> ${to}`);
  });

  lines.push('');
  graph.layers.forEach((layer) => {
    const { style } = layer;
    if (!style) return;
    const id = layerNodeId[layer.name];
    const nodeIds = expandedNodes[layer.name]
      ? layer.files.map((f) => fileNodeId[f])
      : [id];

    lines.push(
      `  classDef ${style.class}_${id} fill:${style.fill},stroke:${style.stroke},stroke-width:1.5px,color:${style.text},rx:8,ry:8`
    );
    lines.push(`  class ${nodeIds.join(',')} ${style.class}_${id}`);
    if (expandedNodes[layer.name]) {
      // The group wrapper sits behind its file boxes, so it is tinted fainter
      // still -- otherwise the two translucent layers stack into a solid block.
      lines.push(
        `  style ${id}_group fill:${style.stroke}12,stroke:${style.stroke}66,stroke-width:1px,color:${style.text}`
      );
    }
  });

  lines.push('  linkStyle default stroke:#64748b,stroke-width:1.5px');
  return lines.join('\n');
}

export { buildMermaidFromGraph };
export default mermaid;
