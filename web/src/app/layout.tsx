import type { Metadata, Viewport } from "next";
import { Hubot_Sans, Martian_Mono, Mona_Sans } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/foothold/nav";
import { Providers } from "@/components/foothold/providers";
import { SiteFooter } from "@/components/foothold/site-footer";
import { ThemeScript } from "@/components/foothold/theme-script";
import { DotField } from "@/components/motion/dot-field";

// Body: Mona Sans. Display: Hubot Sans (width axis for wide/condensed headings). Labels and numbers: Martian Mono.
const monaSans = Mona_Sans({
  variable: "--font-mona-sans",
  subsets: ["latin"],
  display: "swap",
});

const hubotSans = Hubot_Sans({
  variable: "--font-hubot-sans",
  subsets: ["latin"],
  display: "swap",
  axes: ["wdth"],
});

const martianMono = Martian_Mono({
  variable: "--font-martian-mono",
  subsets: ["latin"],
  display: "swap",
  axes: ["wdth"],
});

export const metadata: Metadata = {
  title: { default: "Foothold", template: "%s · Foothold" },
  description:
    "Try the job. Prove the skill. Get the foothold. Career exploration for California's Central Valley.",
  applicationName: "Foothold",
};

export const viewport: Viewport = {
  colorScheme: "dark light",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html data-scroll-behavior="smooth"
      lang="en"
      data-theme="dark"
      suppressHydrationWarning
      className={`${monaSans.variable} ${hubotSans.variable} ${martianMono.variable} antialiased`}
    >
      <head>
        <ThemeScript />
      </head>
      <body className="flex min-h-dvh flex-col">
        <Providers>
          <a
            href="#main"
            className="sr-only text-sm font-medium focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[100] focus:rounded-full focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-foreground"
          >
            Skip to content
          </a>
          <DotField />
          <Nav />
          <main id="main" tabIndex={-1} className="flex flex-1 flex-col outline-none">
            {children}
          </main>
          <SiteFooter />
        </Providers>
      </body>
    </html>
  );
}
