/** @type {import('next').NextConfig} */
const nextConfig = {
  /**
   * Proxy /api/* → FastAPI backend.
   *
   * Local dev:  BACKEND_URL is unset → falls back to http://localhost:8000
   * Production: BACKEND_URL is set in Render env vars to the backend service URL,
   *             e.g. https://mfaq-backend.onrender.com
   *
   * This keeps the browser from ever making cross-origin requests — all calls
   * go to the same origin (/api/...) and Next.js rewrites them server-side.
   */
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
