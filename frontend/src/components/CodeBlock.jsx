import ReactMarkdown from 'react-markdown';
import { Prism as CodeHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

// 🎨 Shared code block renderer (chat markdown + Code Editor tab)
export function CodeBlock({ code, language = 'python' }) {
  if (!code) return null;
  return (
    <CodeHighlighter
      language={language}
      style={vscDarkPlus}
      customStyle={{ background: 'transparent', fontSize: '12px', margin: 0, padding: 0 }}
      wrapLongLines
    >
      {code}
    </CodeHighlighter>
  );
}

// 🎨 Markdown renderer with syntax-highlighted fenced code blocks (used for chat answers)
export function MarkdownWithCode({ content }) {
  return (
    <ReactMarkdown
      components={{
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '');
          if (!match) {
            return <code className="bg-[#0e121f] px-1 py-0.5 rounded text-sky-300 text-[11px]" {...props}>{children}</code>;
          }
          return <CodeBlock code={String(children).replace(/\n$/, '')} language={match[1]} />;
        }
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
