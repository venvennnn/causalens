import type { NextConfig } from "next";

const isExport = process.env.NEXT_OUTPUT === "export";

const nextConfig: NextConfig = {
  images: { unoptimized: true },
};

if (isExport) {
  nextConfig.output = "export";
} else {
  nextConfig.rewrites = async () => [
    {
      source: "/backend/:path*",
      destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/:path*`,
    },
  ];
}

export default nextConfig;
