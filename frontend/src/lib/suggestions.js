// Starter questions for the chat, built from components that were actually
// indexed. Hardcoding examples would break the moment a different repository is
// analyzed, and would suggest questions about code the assistant has never seen.
export function suggestedQuestions(nodeDetails, limit = 3) {
  const components = Object.values(nodeDetails || {}).flatMap((layer) => layer.children || []);
  if (components.length === 0) return [];

  // Skip methods ("Session.get") and private helpers ("_internal"): a question
  // about a top-level class or function reads better and retrieves more.
  const isInteresting = (c) => c.name && !c.name.includes('.') && !c.name.startsWith('_');

  // Rank by how many lines a component spans. A two-line typing protocol is
  // technically a class, but asking about it teaches nothing -- the substantial
  // classes are the ones worth offering.
  const lineSpan = (c) => {
    const [start, end] = String(c.lines || '').split('-').map(Number);
    return Number.isFinite(start) && Number.isFinite(end) ? end - start : 0;
  };
  const bySize = (a, b) => lineSpan(b) - lineSpan(a);

  const classes = components.filter((c) => c.type === 'class' && isInteresting(c)).sort(bySize);
  const functions = components.filter((c) => c.type === 'function' && isInteresting(c)).sort(bySize);

  const seen = new Set();
  const questions = [];
  for (const component of [...classes, ...functions]) {
    if (seen.has(component.name)) continue;
    seen.add(component.name);
    questions.push(
      component.type === 'class'
        ? `What does the ${component.name} class do?`
        : `What does ${component.name}() do?`
    );
    if (questions.length === limit) break;
  }
  return questions;
}
