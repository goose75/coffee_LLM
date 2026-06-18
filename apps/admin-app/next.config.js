/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  transpilePackages: ["@coffee/shared-types", "@coffee/config"],
};
module.exports = nextConfig;
