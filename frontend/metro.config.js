// metro.config.js
const { getDefaultConfig } = require("expo/metro-config");
const path = require('path');
const { FileStore } = require('metro-cache');

const config = getDefaultConfig(__dirname);

// Use a stable on-disk store (shared across web/android)
const root = process.env.METRO_CACHE_ROOT || path.join(__dirname, '.metro-cache');
config.cacheStores = [
  new FileStore({ root: path.join(root, 'cache') }),
];


// // Exclude unnecessary directories from file watching
// config.watchFolders = [__dirname];
// config.resolver.blacklistRE = /(.*)\/(__tests__|android|ios|build|dist|.git|node_modules\/.*\/android|node_modules\/.*\/ios|node_modules\/.*\/windows|node_modules\/.*\/macos)(\/.*)?$/;

// // Alternative: use a more aggressive exclusion pattern
// config.resolver.blacklistRE = /node_modules\/.*\/(android|ios|windows|macos|__tests__|\.git|.*\.android\.js|.*\.ios\.js)$/;

// Reduce the number of workers to decrease resource usage
config.maxWorkers = 2;

// Development only: with RACONTELLE_API_PROXY=http://localhost:8001, Metro relays /api/* to the local API.
// A phone on an `expo start --tunnel` session then reaches the API through the same tunnel as the app.
const apiProxy = process.env.RACONTELLE_API_PROXY;
if (apiProxy) {
  const http = require("http");
  const target = new URL(apiProxy);
  config.server = {
    ...config.server,
    enhanceMiddleware: (middleware) => (req, res, next) => {
      if (!req.url.startsWith("/api/") && req.url !== "/api") return middleware(req, res, next);
      const upstream = http.request(
        {
          hostname: target.hostname,
          port: target.port,
          path: req.url,
          method: req.method,
          headers: { ...req.headers, host: target.host },
        },
        (apiRes) => {
          res.writeHead(apiRes.statusCode || 502, apiRes.headers);
          apiRes.pipe(res);
        },
      );
      upstream.on("error", () => {
        res.writeHead(502, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ detail: "API locale injoignable" }));
      });
      req.pipe(upstream);
    },
  };
}

module.exports = config;
