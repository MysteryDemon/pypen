import type { NextConfig } from "next"
import { PHASE_DEVELOPMENT_SERVER } from "next/constants"

const backend = process.env.PYPEN_BACKEND_URL ?? "http://127.0.0.1:5000"

export default function config(phase: string): NextConfig {
  const nextConfig: NextConfig = {
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
