import { SiteHeader } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowRight, BookOpen, MessagesSquare, Palette } from "lucide-react";
import Link from "next/link";

const steps = [
  {
    icon: BookOpen,
    title: "1. Add knowledge",
    text: "Paste text, upload files, or drop a URL. Your agent indexes it and cites answers.",
  },
  {
    icon: Palette,
    title: "2. Brand it",
    text: "Set a name, welcome message, color, tone and model. Preview instantly in the playground.",
  },
  {
    icon: MessagesSquare,
    title: "3. Embed anywhere",
    text: "Share a hosted page or paste one snippet. API keys and streaming included.",
  },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-white text-gray-900">
      <SiteHeader />
      <main>
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-6 pb-16 pt-20 text-center">
          <p className="mx-auto mb-4 inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs font-medium text-gray-600">
            AI support agents for your business
          </p>
          <h1 className="mx-auto max-w-3xl text-4xl font-semibold tracking-tight text-gray-900 sm:text-5xl">
            Answer customer questions with your own knowledge base
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-gray-500">
            Create a branded chat agent trained on your docs, files and website.
            Embed it on any site in minutes — with citations on every answer.
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <Link href="/signup">
              <Button size="lg">
                Create your agent <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/login">
              <Button size="lg" variant="outline">
                Log in
              </Button>
            </Link>
          </div>
          <p className="mt-4 text-xs text-gray-400">
            Backend: {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"} ·
            Runs locally with your API
          </p>
        </section>

        {/* How it works */}
        <section className="border-t border-gray-200 bg-gray-50/60">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <h2 className="text-center text-2xl font-semibold text-gray-900">
              How it works
            </h2>
            <p className="mx-auto mt-2 max-w-xl text-center text-gray-500">
              Three steps from raw knowledge to a live, embeddable agent.
            </p>
            <div className="mt-10 grid gap-4 md:grid-cols-3">
              {steps.map((s) => (
                <Card key={s.title}>
                  <CardContent className="p-6">
                    <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                      <s.icon className="h-5 w-5" />
                    </span>
                    <h3 className="text-base font-semibold">{s.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-gray-500">{s.text}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="mx-auto max-w-6xl px-6 py-16">
          <Card>
            <CardContent className="flex flex-col items-center gap-4 p-10 text-center">
              <h2 className="text-2xl font-semibold">
                Launch your first agent today
              </h2>
              <p className="max-w-md text-sm text-gray-500">
                Sign up, add one page of knowledge, and share the hosted chat
                link with your team.
              </p>
              <Link href="/signup">
                <Button size="lg">
                  Get started <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>
          <footer className="mt-10 flex items-center justify-between text-xs text-gray-400">
            <span>ChatAPI — minimal business-grade support agents</span>
            <span>Next.js 14 · Tailwind · shadcn-style UI</span>
          </footer>
        </section>
      </main>
    </div>
  );
}
