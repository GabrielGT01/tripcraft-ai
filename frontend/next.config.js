/** @type {import("next").NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Build static HTML/CSS/JS into ./out.
  output: "export",

  // /product/ becomes out/product/index.html.
  trailingSlash: true,
};

module.exports = nextConfig;
