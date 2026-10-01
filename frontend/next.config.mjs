/** @type {import('next').NextConfig} */
const nextConfig = {
  // This project has no ESLint dependency/configuration. Next's implicit lint
  // scan picks up unrelated global rules and treats browser globals/CSS as errors.
  // Type checking and the production compiler still run during `next build`.
  eslint: { ignoreDuringBuilds: true },
  experimental: { proxyTimeout: 120000 },
  outputFileTracingRoot: process.cwd(),
  async rewrites() {
    // In dev the Next server runs on :3000; proxy all API + static asset
    // traffic to the FastAPI backend on :8000 (same as the old Vite proxy).
    return [
      { source: "/api/:path*", destination: `${process.env.BACKEND_INTERNAL_URL || "http://localhost:8000"}/api/:path*` },
      { source: "/static/:path*", destination: `${process.env.BACKEND_INTERNAL_URL || "http://localhost:8000"}/static/:path*` },
    ];
  },
};

export default nextConfig;
