/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  async rewrites() {
    return [
      {
        source: '/api/:path*.php',
        destination: '/api/:path*',
      },
    ];
  },
};

export default nextConfig;
