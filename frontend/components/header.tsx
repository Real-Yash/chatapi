"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bot } from "lucide-react";
import { Button } from "@/components/ui/button";
import { clearToken, getToken } from "@/lib/api";
import { useEffect, useState } from "react";

export function SiteHeader() {
  const router = useRouter();
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    setAuthed(!!getToken());
  }, []);

  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-white">
            <Bot className="h-4 w-4" />
          </span>
          <span className="text-base font-semibold text-gray-900">ChatAPI</span>
        </Link>
        <nav className="flex items-center gap-2">
          {authed ? (
            <>
              <Link href="/dashboard">
                <Button variant="ghost">Dashboard</Button>
              </Link>
              <Button
                variant="outline"
                onClick={() => {
                  clearToken();
                  setAuthed(false);
                  router.push("/");
                }}
              >
                Log out
              </Button>
            </>
          ) : (
            <>
              <Link href="/login">
                <Button variant="ghost">Log in</Button>
              </Link>
              <Link href="/signup">
                <Button>Get started</Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}

export default SiteHeader;
