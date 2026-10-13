/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
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
