"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

/**
 * Renders assistant chat content as styled markdown.
 * Keeps bubbles compact: tight spacing, small text, brand-neutral colors.
 */
export function Markdown({
  text,
  className,
}: {
  text: string;
  className?: string;
}) {
  return (
    <div className={cn("markdown-body text-sm leading-relaxed", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="my-1.5 first:mt-0 last:mb-0">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold text-gray-900">{children}</strong>
          ),
          em: ({ children }) => <em className="text-gray-700">{children}</em>,
          ul: ({ children }) => (
            <ul className="my-1.5 list-disc space-y-1 pl-5 marker:text-gray-400">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="my-1.5 list-decimal space-y-1 pl-5 marker:text-gray-500">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-emerald-700 underline decoration-emerald-300 underline-offset-2 hover:decoration-emerald-600"
            >
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-[12px] text-gray-800">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="my-2 overflow-x-auto rounded-lg bg-gray-900 p-3 font-mono text-[12px] leading-relaxed text-gray-100">
              {children}
            </pre>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-1.5 border-l-2 border-gray-300 pl-3 text-gray-600">
              {children}
            </blockquote>
          ),
          h1: ({ children }) => (
            <p className="mb-1 mt-2 text-sm font-bold text-gray-900 first:mt-0">{children}</p>
          ),
          h2: ({ children }) => (
            <p className="mb-1 mt-2 text-sm font-bold text-gray-900 first:mt-0">{children}</p>
          ),
          h3: ({ children }) => (
            <p className="mb-1 mt-2 text-sm font-semibold text-gray-900 first:mt-0">{children}</p>
          ),
          h4: ({ children }) => (
            <p className="mb-1 mt-2 text-sm font-semibold text-gray-900 first:mt-0">{children}</p>
          ),
          hr: () => <hr className="my-2 border-gray-200" />,
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full border-collapse text-[13px]">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-gray-50">{children}</thead>
          ),
          th: ({ children }) => (
            <th className="border border-gray-200 px-2 py-1 text-left font-semibold text-gray-700">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-gray-200 px-2 py-1 text-gray-700">{children}</td>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
