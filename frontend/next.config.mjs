/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow the Replit reverse proxy to pass through requests
  // without strict host checking in development
  experimental: {
    // No experimental flags needed for MVP
  },
};

export default nextConfig;
