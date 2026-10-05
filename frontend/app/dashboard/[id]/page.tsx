"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Bot,
  Check,
  Copy,
  FileUp,
  Globe,
  KeyRound,
  Link2,
  Plus,
  Send,
  Trash2,
  Type,
} from "lucide-react";
import { SiteHeader } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  getAgent,
  updateAgent,
  deleteAgent,
  listKnowledge,
  addTextKnowledge,
  uploadFileKnowledge,
  addUrlKnowledge,
  deleteKnowledge,
  listApiKeys,
  createApiKey,
  deleteApiKey,
  streamPlaygroundChat,
  getToken,
  type Agent,
  type KnowledgeItem,
  type ApiKey,
  type ChatMessage,
  type Citation,
} from "@/lib/api";

function statusVariant(s: string) {
  if (s === "ready") return "default" as const;
  if (s === "processing") return "warning" as const;
  if (s === "failed") return "destructive" as const;
  return "secondary" as const;
}

export default function AgentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Array.isArray(params?.id) ? params.id[0] : (params?.id as string);

  const [agent, setAgent] = useState<Agent | null>(null);
  const [knowledge, setKnowledge] = useState<KnowledgeItem[]>([]);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refreshKnowledge = useCallback(async () => {
    if (!id) return;
    try {
      setKnowledge(await listKnowledge(id));
    } catch {
      /* non-fatal */
    }
  }, [id]);

  const refreshKeys = useCallback(async () => {
    if (!id) return;
    try {
      setKeys(await listApiKeys(id));
    } catch {
      /* non-fatal */
    }
  }, [id]);

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    if (!id) return;
    (async () => {
      try {
        const [a] = await Promise.all([
          getAgent(id),
          refreshKnowledge(),
          refreshKeys(),
        ]);
        setAgent(a);
      } catch (e: any) {
        setError(e?.message || "Failed to load agent");
      } finally {
        setLoading(false);
      }
    })();
  }, [id, router, refreshKnowledge, refreshKeys]);

  if (loading) {
    return (
      <div className="min-h-screen bg-white">
        <SiteHeader />
        <main className="mx-auto max-w-5xl px-6 py-10">
          <div className="h-6 w-48 animate-pulse rounded bg-gray-100" />
          <div className="mt-6 h-64 animate-pulse rounded-xl bg-gray-50" />
        </main>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="min-h-screen bg-white">
        <SiteHeader />
        <main className="mx-auto max-w-5xl px-6 py-10">
          <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            {error || "Agent not found"}
          </p>
          <Link href="/dashboard">
            <Button variant="outline" className="mt-4">
              <ArrowLeft className="h-4 w-4" /> Back to dashboard
            </Button>
          </Link>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <SiteHeader />
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Link href="/dashboard">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4" /> All agents
          </Button>
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <span
            className="flex h-10 w-10 items-center justify-center rounded-xl text-white"
            style={{ backgroundColor: agent.primary_color || "#059669" }}
          >
            <Bot className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">{agent.name}</h1>
            <p className="text-sm text-gray-500">
              /c/{agent.slug || agent.id}
              {agent.model ? ` · ${agent.model}` : ""}
            </p>
          </div>
        </div>

        {notice ? (
          <p className="mt-4 rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
            {notice}
          </p>
        ) : null}

        <Tabs defaultValue="overview" className="mt-6">
          <TabsList className="flex-wrap">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="playground">Playground</TabsTrigger>
            <TabsTrigger value="knowledge">Knowledge</TabsTrigger>
            <TabsTrigger value="appearance">Appearance</TabsTrigger>
            <TabsTrigger value="api">API</TabsTrigger>
            <TabsTrigger value="embed">Embed</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            <OverviewTab
              agent={agent}
              knowledgeCount={knowledge.length}
              onDeleted={() => router.push("/dashboard")}
              onNotice={setNotice}
            />
          </TabsContent>

          <TabsContent value="playground">
            <PlaygroundTab agentId={agent.id} />
          </TabsContent>

          <TabsContent value="knowledge">
            <KnowledgeTab
              agentId={agent.id}
              items={knowledge}
              onChanged={refreshKnowledge}
              onNotice={setNotice}
            />
          </TabsContent>

          <TabsContent value="appearance">
            <AppearanceTab
              agent={agent}
              onSaved={(a) => {
                setAgent(a);
                setNotice("Appearance saved.");
              }}
            />
          </TabsContent>

          <TabsContent value="api">
            <ApiTab agentId={agent.id} keys={keys} onChanged={refreshKeys} />
          </TabsContent>

          <TabsContent value="embed">
            <EmbedTab agent={agent} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

// ---------------- Overview ----------------

function OverviewTab({
  agent,
  knowledgeCount,
  onDeleted,
  onNotice,
}: {
  agent: Agent;
  knowledgeCount: number;
  onDeleted: () => void;
  onNotice: (s: string) => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const chatUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/c/${agent.slug || agent.id}`
      : `/c/${agent.slug || agent.id}`;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Agent</CardTitle>
          <CardDescription>Core identity and status.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm">
          <Row k="Name" v={agent.name} />
          <Row k="Slug" v={agent.slug || agent.id} />
          <Row k="Model" v={agent.model || "default"} />
          <Row k="Sources" v={String(knowledgeCount)} />
          <div className="flex items-center justify-between">
            <span className="text-gray-500">Status</span>
            <Badge>{agent.status || "active"}</Badge>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Share</CardTitle>
          <CardDescription>Hosted chat page for this agent.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm">
            <Link2 className="h-4 w-4 shrink-0 text-gray-400" />
            <span className="truncate text-gray-700">{chatUrl}</span>
          </div>
          <div className="flex gap-2">
            <Link href={`/c/${agent.slug || agent.id}`} target="_blank">
              <Button variant="outline" size="sm">
                Open chat
              </Button>
            </Link>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                navigator.clipboard?.writeText(chatUrl);
                onNotice("Chat link copied.");
              }}
            >
              <Copy className="h-3.5 w-3.5" /> Copy
            </Button>
          </div>
          <div className="border-t border-gray-100 pt-3">
            <p className="text-sm font-medium text-gray-900">Danger zone</p>
            <p className="text-xs text-gray-500">
              Deleting removes the agent, knowledge and keys.
            </p>
            <Button
              variant="destructive"
              size="sm"
              className="mt-2"
              disabled={deleting}
              onClick={async () => {
                if (!confirm(`Delete agent "${agent.name}"?`)) return;
                setDeleting(true);
                try {
                  await deleteAgent(agent.id);
                  onDeleted();
                } catch (e: any) {
                  onNotice(e?.message || "Delete failed");
                  setDeleting(false);
                }
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
              {deleting ? "Deleting…" : "Delete agent"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-gray-500">{k}</span>
      <span className="font-medium text-gray-900">{v}</span>
    </div>
  );
}

// ---------------- Playground ----------------

function PlaygroundTab({ agentId }: { agentId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

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
    setCitations([]);
    let assistant = "";
    setMessages((m) => [...m, { role: "assistant", content: "" }]);
    try {
      const { citations: c } = await streamPlaygroundChat(agentId, text, next, {
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
    } catch (err: any) {
      assistant = `Error: ${err?.message || "chat failed"}`;
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: assistant };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Playground</CardTitle>
        <CardDescription>
          Test answers with live streaming before publishing.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="chat-scroll flex h-96 flex-col gap-3 overflow-y-auto rounded-lg border border-gray-200 bg-gray-50/50 p-4">
          {messages.length === 0 ? (
            <p className="m-auto text-sm text-gray-400">
              Ask something your customers would ask…
            </p>
          ) : (
            messages.map((m, i) => (
              <div
                key={i}
                className={
                  m.role === "user"
                    ? "ml-auto max-w-[80%] rounded-xl bg-emerald-600 px-3 py-2 text-sm text-white"
                    : "mr-auto max-w-[85%] rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"
                }
              >
                {m.content || (busy && i === messages.length - 1 ? "…" : "")}
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
        {citations.length > 0 ? (
          <div className="mt-3 rounded-lg border border-gray-200 p-3">
            <p className="text-xs font-medium text-gray-500">CITATIONS</p>
            <ul className="mt-1 flex flex-col gap-1">
              {citations.map((c, i) => (
                <li key={i} className="text-xs text-gray-600">
                  [{i + 1}] {c.title || c.url || "source"}
                  {c.snippet ? ` — ${c.snippet.slice(0, 120)}` : ""}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <form onSubmit={send} className="mt-3 flex gap-2">
          <Input
            placeholder="Type a message…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={busy}
          />
          <Button type="submit" disabled={busy || !input.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

// ---------------- Knowledge ----------------

function KnowledgeTab({
  agentId,
  items,
  onChanged,
  onNotice,
}: {
  agentId: string;
  items: KnowledgeItem[];
  onChanged: () => void;
  onNotice: (s: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);

  async function addText(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;
    setBusy("text");
    try {
      await addTextKnowledge(agentId, { title: title.trim(), content: content.trim() });
      setTitle("");
      setContent("");
      onChanged();
      onNotice("Text source added.");
    } catch (e: any) {
      onNotice(e?.message || "Failed to add text");
    } finally {
      setBusy(null);
    }
  }

  async function addUrl(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setBusy("url");
    try {
      await addUrlKnowledge(agentId, { url: url.trim() });
      setUrl("");
      onChanged();
      onNotice("URL queued for scraping.");
    } catch (e: any) {
      onNotice(e?.message || "Failed to add URL");
    } finally {
      setBusy(null);
    }
  }

  async function uploadFile(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy("file");
    try {
      await uploadFileKnowledge(agentId, file);
      setFile(null);
      (document.getElementById("kb-file") as HTMLInputElement | null)?.value &&
        (((document.getElementById("kb-file") as HTMLInputElement).value = ""));
      onChanged();
      onNotice("File uploaded.");
    } catch (e: any) {
      onNotice(e?.message || "Upload failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Type className="h-4 w-4" /> Manual text
            </CardTitle>
            <CardDescription>Paste FAQs, policies, notes.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={addText} className="flex flex-col gap-2">
              <Input
                placeholder="Title e.g. Refund policy"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
              <Textarea
                placeholder="Content…"
                value={content}
                onChange={(e) => setContent(e.target.value)}
              />
              <Button type="submit" size="sm" disabled={busy === "text"}>
                {busy === "text" ? "Adding…" : "Add text"}
              </Button>
            </form>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileUp className="h-4 w-4" /> File upload
            </CardTitle>
            <CardDescription>PDF, TXT, MD, DOCX.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={uploadFile} className="flex flex-col gap-2">
              <Input
                id="kb-file"
                type="file"
                accept=".pdf,.txt,.md,.markdown,.docx"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              {file ? (
                <p className="text-xs text-gray-500">{file.name}</p>
              ) : null}
              <Button type="submit" size="sm" disabled={!file || busy === "file"}>
                {busy === "file" ? "Uploading…" : "Upload file"}
              </Button>
            </form>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-4 w-4" /> URL scrape
            </CardTitle>
            <CardDescription>Index a public page.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={addUrl} className="flex flex-col gap-2">
              <Input
                placeholder="https://example.com/pricing"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
              <Button type="submit" size="sm" disabled={busy === "url"}>
                {busy === "url" ? "Queueing…" : "Scrape URL"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Sources ({items.length})</CardTitle>
          <CardDescription>Status updates after indexing runs.</CardDescription>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <p className="text-sm text-gray-400">
              No sources yet — add text, a file, or a URL above.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {items.map((k) => (
                <li
                  key={k.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-900">
                      {k.title}
                    </p>
                    <p className="truncate text-xs text-gray-500">
                      {k.type}
                      {k.url ? ` · ${k.url}` : ""}
                      {k.file_name ? ` · ${k.file_name}` : ""}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge variant={statusVariant(k.status)}>{k.status}</Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={async () => {
                        if (!confirm(`Delete "${k.title}"?`)) return;
                        try {
                          await deleteKnowledge(agentId, k.id);
                          onChanged();
                        } catch (e: any) {
                          onNotice(e?.message || "Delete failed");
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------- Appearance ----------------

function AppearanceTab({
  agent,
  onSaved,
}: {
  agent: Agent;
  onSaved: (a: Agent) => void;
}) {
  const [name, setName] = useState(agent.name || "");
  const [welcome, setWelcome] = useState(
    agent.welcome_message || "Hi! How can I help you today?"
  );
  const [color, setColor] = useState(agent.primary_color || "#059669");
  const [tone, setTone] = useState(agent.tone || "helpful");
  const [model, setModel] = useState(agent.model || "qwen/qwen3.8-27b:free");
  const [saving, setSaving] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await updateAgent(agent.id, {
        name,
        welcome_message: welcome,
        primary_color: color,
        tone,
        model,
      });
      onSaved({ ...agent, ...updated });
    } catch {
      onSaved({ ...agent, name, welcome_message: welcome, primary_color: color, tone, model });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Branding</CardTitle>
          <CardDescription>Shown on the hosted chat page.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={save} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ap-name">Name</Label>
              <Input id="ap-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ap-welcome">Welcome message</Label>
              <Textarea
                id="ap-welcome"
                value={welcome}
                onChange={(e) => setWelcome(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="ap-color">Primary color</Label>
                <div className="flex items-center gap-2">
                  <input
                    id="ap-color"
                    type="color"
                    value={color}
                    onChange={(e) => setColor(e.target.value)}
                    className="h-10 w-12 cursor-pointer rounded border border-gray-200"
                  />
                  <Input value={color} onChange={(e) => setColor(e.target.value)} />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="ap-tone">Tone</Label>
                <Input id="ap-tone" value={tone} onChange={(e) => setTone(e.target.value)} placeholder="helpful, formal, friendly…" />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ap-model">Model</Label>
              <Input id="ap-model" value={model} onChange={(e) => setModel(e.target.value)} placeholder="qwen/qwen3.8-27b:free" />
            </div>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save appearance"}
            </Button>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Preview</CardTitle>
          <CardDescription>How the header looks to visitors.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-hidden rounded-xl border border-gray-200">
            <div
              className="flex items-center gap-2 px-4 py-3 text-white"
              style={{ backgroundColor: color }}
            >
              <Bot className="h-4 w-4" />
              <span className="text-sm font-semibold">{name || "Agent"}</span>
            </div>
            <div className="bg-gray-50 p-4">
              <div className="max-w-[85%] rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800">
                {welcome}
              </div>
              <p className="mt-2 text-xs text-gray-400">Tone: {tone} · Model: {model}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------- API keys ----------------

function ApiTab({
  agentId,
  keys,
  onChanged,
}: {
  agentId: string;
  keys: ApiKey[];
  onChanged: () => void;
}) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const res: any = await createApiKey(agentId, { name: name.trim() });
      const full = res?.key || res?.api_key || res?.token || res?.value || null;
      setNewKey(full);
      setName("");
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="h-4 w-4" /> API keys
        </CardTitle>
        <CardDescription>Authenticate server-side chat calls.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <form onSubmit={create} className="flex gap-2">
          <Input
            placeholder="Key name e.g. production"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Button type="submit" disabled={busy || !name.trim()}>
            <Plus className="h-4 w-4" /> {busy ? "…" : "Create"}
          </Button>
        </form>
        {newKey ? (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
            <p className="text-xs font-medium text-emerald-800">
              Copy this key now — it will not be shown again.
            </p>
            <div className="mt-2 flex items-center gap-2">
              <code className="flex-1 truncate rounded bg-white px-2 py-1 text-xs">
                {newKey}
              </code>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  navigator.clipboard?.writeText(newKey);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }}
              >
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              </Button>
            </div>
          </div>
        ) : null}
        {keys.length === 0 ? (
          <p className="text-sm text-gray-400">No API keys yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {keys.map((k) => (
              <li
                key={k.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 px-3 py-2"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900">{k.name}</p>
                  <p className="text-xs text-gray-500">
                    {(k.key_prefix || k.prefix || "••••") + "••••"}
                    {k.created_at ? ` · ${k.created_at.slice(0, 10)}` : ""}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={async () => {
                    if (!confirm(`Delete key "${k.name}"?`)) return;
                    await deleteApiKey(agentId, k.id);
                    onChanged();
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------- Embed ----------------

function EmbedTab({ agent }: { agent: Agent }) {
  const slug = agent.slug || agent.id;
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const chatUrl = `${origin}/c/${slug}?embed=true`;
  const iframe = `<iframe\n  src="${chatUrl}"\n  width="380"\n  height="600"\n  style="border:1px solid #e5e7eb;border-radius:12px;"\n  allow="clipboard-write"\n/>`;
  const script = `<script src="${origin}/widget.js" data-agent="${slug}" data-base="${origin}"><\/script>`;
  const [copied, setCopied] = useState<string | null>(null);

  function copy(text: string, which: string) {
    navigator.clipboard?.writeText(text);
    setCopied(which);
    setTimeout(() => setCopied(null), 1500);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Embed</CardTitle>
        <CardDescription>Put this agent on any website.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
          <p className="text-xs font-medium text-gray-500">HOSTED PAGE</p>
          <p className="mt-1 truncate text-sm text-gray-800">
            {origin}/c/{slug}
          </p>
        </div>
        <div className="flex gap-2">
          <Dialog>
            <DialogTrigger asChild>
              <Button>
                <Copy className="h-4 w-4" /> Get embed code
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Embed {agent.name}</DialogTitle>
                <DialogDescription>
                  Paste one of these snippets into your site.
                </DialogDescription>
              </DialogHeader>
              <div className="flex flex-col gap-4">
                <div>
                  <p className="mb-1 text-sm font-medium">Iframe (recommended)</p>
                  <pre className="overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs text-gray-100">
                    {iframe}
                  </pre>
                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-2"
                    onClick={() => copy(iframe, "iframe")}
                  >
                    {copied === "iframe" ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                    {copied === "iframe" ? " Copied" : " Copy iframe"}
                  </Button>
                </div>
                <div>
                  <p className="mb-1 text-sm font-medium">Floating widget</p>
                  <pre className="overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs text-gray-100">
                    {script}
                  </pre>
                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-2"
                    onClick={() => copy(script, "script")}
                  >
                    {copied === "script" ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                    {copied === "script" ? " Copied" : " Copy script"}
                  </Button>
                </div>
              </div>
              <DialogFooter>
                <p className="text-xs text-gray-400">
                  Append ?embed=true for compact mode without outer chrome.
                </p>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Link href={`/c/${slug}?embed=true`} target="_blank">
            <Button variant="outline">Preview compact</Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
