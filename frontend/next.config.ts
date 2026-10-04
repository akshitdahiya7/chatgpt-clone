import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained server bundle so the runtime image does not need
  // node_modules or the source tree.
  output: "standalone",
};

export default nextConfig;
