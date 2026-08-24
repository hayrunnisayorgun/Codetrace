const EXTENSION_TO_LANGUAGE = {
  py: 'python',
  js: 'javascript',
  jsx: 'jsx',
  ts: 'typescript',
  tsx: 'tsx',
  json: 'json',
  md: 'markdown',
  css: 'css',
  html: 'html',
  sh: 'bash',
  yml: 'yaml',
  yaml: 'yaml',
};

// File extension -> Prism language, for highlighting in the Code Editor tab.
// Defaults to python because only Python files are indexed today.
export function languageFromFilePath(filePath) {
  const ext = (filePath || '').split('.').pop().toLowerCase();
  return EXTENSION_TO_LANGUAGE[ext] || 'python';
}
