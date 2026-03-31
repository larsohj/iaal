/**
 * Cloudflare Worker: proxy for cinema-api.com
 *
 * GitHub Actions IPs er blokkert av cinema-api.com.
 * Denne workeren videresender requests via Cloudflare sine egne IPs.
 *
 * Deploy:  cd cloudflare-worker && wrangler deploy
 * Test:    curl "https://iaal-odeon-proxy.<subdomain>.workers.dev/show/stripped/no/1/1024/?CountryAlias=no&CityAlias=AL&Channel=Web"
 */

const UPSTREAM = "https://services.cinema-api.com";

const ALLOWED_PATH_PREFIXES = [
  "/show/stripped/",
  "/movie/scheduled/",
];

export default {
  async fetch(request) {
    const url = new URL(request.url);

    const allowed = ALLOWED_PATH_PREFIXES.some(p => url.pathname.startsWith(p));
    if (!allowed) {
      return new Response("Not found", { status: 404 });
    }

    const upstream = new URL(url.pathname + url.search, UPSTREAM);

    const proxied = await fetch(upstream.toString(), {
      method: "GET",
      headers: {
        "User-Agent":
          "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " +
          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Origin": "https://www.odeonkino.no",
        "Referer": "https://www.odeonkino.no/",
        "Accept": "application/json",
      },
    });

    const body = await proxied.arrayBuffer();
    return new Response(body, {
      status: proxied.status,
      headers: {
        "Content-Type": proxied.headers.get("Content-Type") || "application/json",
        "Cache-Control": "no-store",
      },
    });
  },
};
