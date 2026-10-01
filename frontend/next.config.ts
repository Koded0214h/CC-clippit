import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  agentRules: false,
  allowedDevOrigins: ["127.0.0.1", "10.115.136.123"],
  images: {
    // Campaign covers, brand/creator photos and asset uploads all come
    // from Cloudinary now. next/image refuses to render an unlisted
    // remote host at all (not a broken-image icon — it just never
    // renders), which is why these went blank the moment uploads moved
    // off local disk.
    remotePatterns: [{ protocol: "https", hostname: "res.cloudinary.com" }],
  },
  async headers() {
    return [
      {
        source: "/assets/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=86400, stale-while-revalidate=604800",
          },
        ],
      },
      {
        source: "/landing-runtime.js",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=3600, stale-while-revalidate=86400",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
