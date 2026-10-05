"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Bot, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  getPublicAgent,
  streamPublicChat,
  type Agent,
  type ChatMessage,
  type Citation,
} from "@/lib/api";

export default function PublicChat({ slug }: { slug: string }) {
  const search = useSearchParams();
  const embed = search.get("embed") === "true";

  const [agent, setAgent] = useState<Agent | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const color = agent?.primary_color || "#059669";
  const welcome =
    agent?.welcome_message || "Hi! How can I help you today?";

  useEffect(() => {
    getPublicAgent(slug)
      .then((a) => {
        setAgent(a);
        setMessages([{ role: "assistant", content: a.welcome_message || welcome }]);
      })
      .catch(() => {
        // Public endpoint may not exist yet — fall back to slug-only mode
        setAgent({ id: slug, name: slug, slug } as Agent);
        setMessages([{ role: "assistant", content: welcome }]);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    const next = [...messages, { role: "user" as const, content: text }];
    setMessages(next);
    setInput("");
    setBusy(true);
    setError("");
    setCitations([]);
    let assistant = "";
    setMessages((m) => [...m, { role: "assistant", content: "" }]);
    try {
      const { citations: c } = await streamPublicChat(slug, text, next, {
        onToken: (t) => {
          assistant += t;
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { role: "assistant", content: assistant };
            return copy;
          });
        },
        onCitations: (cits) => setCitations(cits),
      });
      if (c?.length) setCitations(c);
      if (!assistant) {
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = {
            role: "assistant",
            content: "Sorry — I could not generate a response.",
          };
          return copy;
        });
      }
    } catch (err: any) {
      setError(err?.message || "Chat failed");
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = {
          role: "assistant",
          content: "Something went wrong. Please try again.",
        };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={cn(
        "flex min-h-screen flex-col bg-white text-gray-900",
        embed && "min-h-0"
      )}
    >
      {!embed ? (
        <header className="border-b border-gray-200">
          <div className="mx-auto flex h-14 max-w-3xl items-center gap-2 px-4">
            <span
              className="flex h-8 w-8 items-center justify-center rounded-lg text-white"
              style={{ backgroundColor: color }}
            >
              <Bot className="h-4 w-4" />
            </span>
            <span className="text-sm font-semibold">
              {agent?.name || slug}
            </span>
          </div>
        </header>
      ) : null}

      <main
        className={cn(
          "mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-4",
          embed && "px-3 py-3"
        )}
      >
        {/* Branded header inside embed mode */}
        <div
          className="mb-3 flex items-center gap-2 rounded-xl px-4 py-3 text-white"
          style={{ backgroundColor: color }}
        >
          <Bot className="h-4 w-4" />
          <div>
            <p className="text-sm font-semibold leading-none">
              {agent?.name || slug}
            </p>
            <p className="mt-1 text-xs opacity-80">Typically replies instantly</p>
          </div>
        </div>

        {error ? (
          <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        ) : null}

        <div className="chat-scroll flex h-[52vh] flex-col gap-3 overflow-y-auto rounded-xl border border-gray-200 bg-gray-50/50 p-4">
          {messages.map((m, i) => (
            <div
              key={i}
              className={
                m.role === "user"
                  ? "ml-auto max-w-[80%] rounded-xl px-3 py-2 text-sm text-white"
                  : "mr-auto max-w-[85%] rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"
              }
              style={m.role === "user" ? { backgroundColor: color } : undefined}
            >
              {m.content || (busy && i === messages.length - 1 ? "…" : "")}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {citations.length > 0 ? (
          <div className="mt-3 rounded-xl border border-gray-200 p-3">
            <p className="text-xs font-medium text-gray-500">SOURCES</p>
            <ul className="mt-1 flex flex-col gap-1">
              {citations.map((c, i) => (
                <li key={i} className="text-xs text-gray-600">
                  [{i + 1}]{" "}
                  {c.url ? (
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noreferrer"
                      className="underline"
                    >
                      {c.title || c.url}
                    </a>
                  ) : (
                    c.title || "source"
                  )}
                  {c.snippet ? ` — ${c.snippet.slice(0, 140)}` : ""}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <form onSubmit={send} className="mt-3 flex gap-2">
          <Input
            placeholder="Ask a question…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={busy}
          />
          <Button type="submit" disabled={busy || !input.trim()} style={{ backgroundColor: color }}>
            <Send className="h-4 w-4" />
          </Button>
        </form>
        {!embed ? (
          <p className="mt-3 text-center text-xs text-gray-400">
            Powered by ChatAPI
          </p>
        ) : null}
      </main>
    </div>
  );
}
