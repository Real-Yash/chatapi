"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Bot, ArrowRight } from "lucide-react";
import { SiteHeader } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { listAgents, createAgent, getToken, type Agent } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [redirecting, setRedirecting] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      setRedirecting(true);
      setLoading(false);
      router.push("/login");
      return;
    }
    listAgents()
      .then(setAgents)
      .catch((e: any) => setError(e?.message || "Failed to load agents"))
      .finally(() => setLoading(false));
  }, [router]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      const agent = await createAgent({ name: name.trim() });
      setAgents((a) => [agent, ...a]);
      setName("");
      setOpen(false);
      if (agent?.id) router.push(`/dashboard/${agent.id}`);
    } catch (err: any) {
      setError(err?.message || "Failed to create agent");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Agents</h1>
            <p className="mt-1 text-sm text-gray-500">
              Create and manage branded support agents.
            </p>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4" /> New agent
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create agent</DialogTitle>
                <DialogDescription>
                  Give your agent a working name. You can brand it later.
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={onCreate} className="flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="agent-name">Name</Label>
                  <Input
                    id="agent-name"
                    placeholder="e.g. Acme Support"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <DialogFooter>
                  <Button type="submit" disabled={creating || !name.trim()}>
                    {creating ? "Creating…" : "Create agent"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {error ? (
          <p className="mt-6 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </p>
        ) : null}

        {redirecting ? (
          <p className="mt-8 text-sm text-gray-500">
            Not signed in — redirecting to login…
          </p>
        ) : loading ? (
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Card key={i}>
                <CardContent className="p-6">
                  <div className="h-5 w-2/3 animate-pulse rounded bg-gray-100" />
                  <div className="mt-3 h-4 w-1/2 animate-pulse rounded bg-gray-100" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : agents.length === 0 ? (
          <Card className="mt-8">
            <CardContent className="flex flex-col items-center gap-3 p-12 text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-gray-100 text-gray-500">
                <Bot className="h-6 w-6" />
              </span>
              <h2 className="text-base font-semibold">No agents yet</h2>
              <p className="max-w-sm text-sm text-gray-500">
                Create your first agent, add knowledge, and share the hosted
                chat link.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {agents.map((a) => (
              <Card key={a.id} className="transition-shadow hover:shadow-md">
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <span
                      className="flex h-9 w-9 items-center justify-center rounded-lg text-white"
                      style={{ backgroundColor: a.primary_color || "#059669" }}
                    >
                      <Bot className="h-4 w-4" />
                    </span>
                    {a.status ? (
                      <Badge variant="secondary">{a.status}</Badge>
                    ) : (
                      <Badge>active</Badge>
                    )}
                  </div>
                  <CardTitle className="mt-2">{a.name}</CardTitle>
                  <CardDescription>
                    /c/{a.slug || a.id}
                    {a.model ? ` · ${a.model}` : ""}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex items-center gap-2">
                  <Link href={`/dashboard/${a.id}`} className="flex-1">
                    <Button variant="outline" className="w-full">
                      Manage <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Link>
                  <Link href={`/c/${a.slug || a.id}`} target="_blank">
                    <Button variant="ghost">Preview</Button>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
