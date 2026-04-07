import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:5050/api/:path*",
      },
      {
        source: "/login",
        destination: "http://localhost:5050/login",
      },
      {
        source: "/signup",
        destination: "http://localhost:5050/signup",
      },
      {
        source: "/logout",
        destination: "http://localhost:5050/logout",
      },
    ];
  },
};

export default nextConfig;
