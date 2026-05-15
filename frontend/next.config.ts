import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "api.lorcana.ravensburger.com",
        pathname: "/images/**",
      },
    ],
  },
};

export default nextConfig;
