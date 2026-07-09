"""Deterministic Next.js scaffold: config files + a guaranteed-to-build core component
library (Button, Card, Container, Badge, Input). Keeping these five deterministic means
the generated project always compiles even before any LLM-authored page/block code is
added on top -- the LLM (Frontend Developer Agent) is responsible for everything else:
header/footer, every page, page-specific blocks, and any *extra* primitives the UI
Components Agent asked for beyond these five.
"""
from __future__ import annotations

from typing import Any, Dict


def _dig(d: dict, *path, default=""):
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key, {})
    return cur if cur != {} else default


def get_scaffold_files(tokens: Dict[str, Any], project_name: str, tagline: str, slug: str) -> Dict[str, str]:
    ds = tokens.get("design_system", {}) or {}
    color = tokens.get("color", {}) or {}
    palette = color.get("palette", {}) or {}
    light = color.get("light", {}) or {}
    dark = color.get("dark", {}) or {}
    font = ds.get("font", {}) or {}
    radius = ds.get("radius", {}) or {}
    grid = ds.get("grid", {}) or {}

    family = font.get("family") or "Vazirmatn"
    google_import = font.get("google_font_import") or "Vazirmatn:wght@400;500;600;700;800"
    fallback = font.get("fallback") or "Tahoma, sans-serif"
    max_width = grid.get("container_max_width") or "1200px"

    def g(d, key, fallback_v):
        return d.get(key) or fallback_v

    files: Dict[str, str] = {}

    npm_name = "".join(c if (c.isalnum() or c == "-") else "-" for c in slug.lower()) or "deepagent-site"

    files["package.json"] = f"""{{
  "name": "{npm_name}",
  "version": "0.1.0",
  "private": true,
  "scripts": {{
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  }},
  "dependencies": {{
    "next": "^14.2.30",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "next-themes": "^0.3.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.2",
    "lucide-react": "^0.451.0"
  }},
  "devDependencies": {{
    "typescript": "^5.5.4",
    "@types/node": "^20.14.15",
    "@types/react": "^18.3.4",
    "@types/react-dom": "^18.3.0",
    "tailwindcss": "^3.4.10",
    "postcss": "^8.4.41",
    "autoprefixer": "^10.4.20",
    "eslint": "^8.57.0",
    "eslint-config-next": "^14.2.30"
  }}
}}
"""

    files["tsconfig.json"] = """{
  "compilerOptions": {
    "target": "es2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
"""

    files["next-env.d.ts"] = """/// <reference types="next" />
/// <reference types="next/image-types/global" />
"""

    files["next.config.mjs"] = """/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    // The Frontend Developer Agent's output is reviewed by the Code Review Agent
    // separately; don't let lint warnings hard-fail the production build.
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
"""

    files["postcss.config.js"] = """module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
"""

    files["tailwind.config.ts"] = f"""import type {{ Config }} from "tailwindcss";

const config: Config = {{
  darkMode: "class",
  content: ["./app/**/*.{{ts,tsx}}", "./components/**/*.{{ts,tsx}}"],
  theme: {{
    container: {{
      center: true,
      padding: "1rem",
    }},
    extend: {{
      maxWidth: {{
        container: "{max_width}",
      }},
      colors: {{
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: "var(--card)",
        border: "var(--border)",
        muted: "var(--muted)",
        primary: "var(--primary)",
        "primary-foreground": "var(--primary-foreground)",
        secondary: "var(--secondary)",
        accent: "var(--accent)",
        success: "var(--success)",
        warning: "var(--warning)",
        error: "var(--error)",
      }},
      borderRadius: {{
        sm: "{g(radius, 'sm', '6px')}",
        md: "{g(radius, 'md', '10px')}",
        lg: "{g(radius, 'lg', '16px')}",
        full: "{g(radius, 'full', '9999px')}",
      }},
      fontFamily: {{
        sans: ["var(--font-sans)"],
      }},
    }},
  }},
  plugins: [],
}};

export default config;
"""

    files["app/globals.css"] = f"""@import url('https://fonts.googleapis.com/css2?family={google_import}&display=swap');
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {{
  --background: {g(light, 'background', '#FFFFFF')};
  --foreground: {g(light, 'foreground', '#0B0B0F')};
  --card: {g(light, 'card', '#F8FAFC')};
  --border: {g(light, 'border', '#E2E8F0')};
  --muted: {g(light, 'muted', '#64748B')};
  --success: {g(light, 'success', '#16A34A')};
  --warning: {g(light, 'warning', '#D97706')};
  --error: {g(light, 'error', '#DC2626')};
  --primary: {g(palette, 'primary', '#4F46E5')};
  --primary-foreground: {g(palette, 'primary_foreground', '#FFFFFF')};
  --secondary: {g(palette, 'secondary', '#F59E0B')};
  --accent: {g(palette, 'accent', '#10B981')};
  --font-sans: '{family}', {fallback};
}}

.dark {{
  --background: {g(dark, 'background', '#0B0B0F')};
  --foreground: {g(dark, 'foreground', '#F8FAFC')};
  --card: {g(dark, 'card', '#151519')};
  --border: {g(dark, 'border', '#27272A')};
  --muted: {g(dark, 'muted', '#94A3B8')};
  --success: {g(dark, 'success', '#22C55E')};
  --warning: {g(dark, 'warning', '#F59E0B')};
  --error: {g(dark, 'error', '#EF4444')};
}}

* {{
  border-color: var(--border);
}}

html {{
  scroll-behavior: smooth;
}}

body {{
  background-color: var(--background);
  color: var(--foreground);
  font-family: var(--font-sans);
}}
"""

    files["app/layout.tsx"] = f"""import type {{ Metadata }} from "next";
import "./globals.css";
import {{ ThemeProvider }} from "@/components/theme-provider";
import {{ Header }} from "@/components/blocks/header";
import {{ Footer }} from "@/components/blocks/footer";

export const metadata: Metadata = {{
  title: "{project_name}",
  description: "{tagline}",
}};

export default function RootLayout({{
  children,
}}: {{
  children: React.ReactNode;
}}) {{
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem={{false}}>
          <Header />
          <main className="min-h-screen">{{children}}</main>
          <Footer />
        </ThemeProvider>
      </body>
    </html>
  );
}}
"""

    files["lib/utils.ts"] = """import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
"""

    files["components/theme-provider.tsx"] = """"use client";

import * as React from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

export function ThemeProvider({
  children,
  ...props
}: React.ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
"""

    files["components/theme-toggle.tsx"] = """"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  if (!mounted) {
    return <div className="h-9 w-9" />;
  }

  return (
    <Button
      variant="ghost"
      className="h-9 w-9 p-0"
      aria-label="تغییر تم روشن/تاریک"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
"""

    files["components/ui/button.tsx"] = """import * as React from "react";
import { cn } from "@/lib/utils";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "outline";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-foreground hover:opacity-90",
  secondary: "bg-secondary text-primary-foreground hover:opacity-90",
  ghost: "bg-transparent hover:bg-card",
  outline: "border border-border bg-transparent hover:bg-card",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-transform hover:scale-[1.02] disabled:pointer-events-none disabled:opacity-50",
          variantClasses[variant],
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
"""

    files["components/ui/card.tsx"] = """import * as React from "react";
import { cn } from "@/lib/utils";

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-lg border border-border bg-card p-6 shadow-sm transition-shadow hover:shadow-md",
        className
      )}
      {...props}
    />
  )
);
Card.displayName = "Card";
"""

    files["components/ui/container.tsx"] = """import * as React from "react";
import { cn } from "@/lib/utils";

export const Container = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("mx-auto w-full max-w-container px-4", className)} {...props} />
  )
);
Container.displayName = "Container";
"""

    files["components/ui/badge.tsx"] = """import * as React from "react";
import { cn } from "@/lib/utils";

export type BadgeVariant = "default" | "success" | "warning" | "error";

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-border text-foreground",
  success: "bg-success text-primary-foreground",
  warning: "bg-warning text-primary-foreground",
  error: "bg-error text-primary-foreground",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-3 py-1 text-xs font-medium",
        variantClasses[variant],
        className
      )}
      {...props}
    />
  );
}
"""

    files["components/ui/input.tsx"] = """import * as React from "react";
import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";
"""

    files["components/ui/textarea.tsx"] = """import * as React from "react";
import { cn } from "@/lib/utils";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "flex min-h-24 w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);
Textarea.displayName = "Textarea";
"""

    files["components/ui/photo-credit.tsx"] = """import credits from "@/public/images/credits.json";

interface CreditEntry {
  photographer: string;
  photographerUrl: string;
}

export function PhotoCredit({ slug, className }: { slug: string; className?: string }) {
  const entry = (credits as Record<string, CreditEntry>)[slug];
  if (!entry) return null;
  return (
    <a
      href={`${entry.photographerUrl}?utm_source=deepagent&utm_medium=referral`}
      target="_blank"
      rel="noopener noreferrer"
      className={
        className ??
        "absolute bottom-2 right-2 z-10 rounded bg-black/50 px-2 py-1 text-xs text-white hover:underline"
      }
    >
      عکس: {entry.photographer} / Unsplash
    </a>
  );
}
"""

    # Always present (even empty) so the static `import credits from ".../credits.json"`
    # in photo-credit.tsx never fails the build, whether or not hero_images_skill ran.
    files["public/images/credits.json"] = "{}\n"

    files[".eslintrc.json"] = """{
  "extends": "next/core-web-vitals"
}
"""

    # Barrel export so both `@/components/ui/button` and `@/components/ui` import
    # styles resolve -- LLM-generated code sometimes uses the folder-level import.
    files["components/ui/index.ts"] = (
        'export * from "./button";\n'
        'export * from "./card";\n'
        'export * from "./container";\n'
        'export * from "./badge";\n'
        'export * from "./input";\n'
        'export * from "./textarea";\n'
        'export * from "./photo-credit";\n'
    )

    return files


CORE_PRIMITIVE_NAMES = {
    "button", "card", "container", "section", "badge", "input", "textarea", "photo-credit",
}
