import type { NextConfig } from "next"
import { PHASE_DEVELOPMENT_SERVER } from "next/constants"

// The Quart server that `npm run dev` forwards API calls to.
const backend = process.env.PYPEN_BACKEND_URL ?? "http://127.0.0.1:5000"

export default function config(phase: string): NextConfig {
  const nextConfig: NextConfig = {
    // `next build` writes a static site to out/, which Quart serves.
    output: "export",
    images: { unoptimized: true },
    turbopack: {
      rules: {
        "*.css": {
          loaders: ["@tailwindcss/turbopack"],
          as: "*.css",
        },
      },
    },
  }

  if (phase === PHASE_DEVELOPMENT_SERVER) {
    // socket.io polls `/socket.io/?EIO=...`; keep the trailing slash intact.
    nextConfig.skipTrailingSlashRedirect = true
    nextConfig.rewrites = async () => [
      { source: "/service/:path*", destination: `${backend}/service/:path*` },
      { source: "/auth/:path*", destination: `${backend}/auth/:path*` },
      { source: "/logout", destination: `${backend}/logout` },
      { source: "/socket.io/", destination: `${backend}/socket.io/` },
    ]
  }

  return nextConfig
}
