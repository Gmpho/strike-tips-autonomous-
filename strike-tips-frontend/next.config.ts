import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Use Turbopack settings
  turbopack: {},
  // Enable View Transitions for smooth page/tab morphing
  experimental: {
    viewTransition: true,
  },
};

export default nextConfig;
