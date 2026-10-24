import type { NextConfig } from "next";

// Static export for Netlify only when NEXT_OUTPUT=export (scripts/build_web_static.sh);
// `next dev` and normal builds are unaffected. NEXT_DIST_DIR keeps the export build
// out of .next so it never clobbers a running dev server.
const isExport = process.env.NEXT_OUTPUT === "export";

const nextConfig: NextConfig = {
  // PPR (cacheComponents / partialPrefetching) cannot run in export mode.
  cacheComponents: !isExport,
  partialPrefetching: !isExport,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
  ...(isExport ? { output: "export" as const, images: { unoptimized: true }, trailingSlash: true } : {}),
};

export default nextConfig;
