# God's Eye View integration

HOMER integrates the upstream **God's Eye View** JavaScript/Cesium application as a
separate local workspace. The desktop sidebar launcher checks whether the local
service is already running, starts it when needed, waits for its HTTP response,
and opens the browser only after it is ready.

## Install once

Keep the upstream project beside HOMER (recommended) or set HOMER_GLOBE_DIR
in HOMER's local .env file:

~~~powershell
cd D:\Software
git clone https://github.com/bilawalsidhu/gods-eye-view.git
cd gods-eye-view
npm ci
npm run doctor
~~~

The upstream project currently requires Node.js >=24.14 <25 or >=26 <27.
Node 24.22.x is supported. HOMER does not install Node or run npm ci
automatically; dependency installation is a one-time setup step.

After installation, start HOMER normally and click **God's Eye View**. HOMER
starts the local Vite server bound to 127.0.0.1 on port 4173 by default,
waits up to 30 seconds, and opens the globe when it responds. If the service is
already running, HOMER reuses it. If you use another local port, set
`HOMER_GLOBE_URL=http://127.0.0.1:PORT`. If the checkout is elsewhere, set
HOMER_GLOBE_DIR=D:\path\\to\\gods-eye-view.

## What HOMER verifies

- URL is HTTP and loopback-only; remote hosts and credential-bearing URLs
  are rejected.
- Upstream checkout, package.json, dev script and node_modules exist.
- Node version matches the upstream engine requirement.
- Vite is started without a shell, bound to loopback, with a strict port.
- The browser opens only after the local server responds successfully.

If startup fails, run npm run doctor in the globe folder and verify port 4173
is free. HOMER reports missing dependencies, unsupported Node versions, and
startup timeouts in its status bar. If Vite exits during startup, inspect `.homer-globe.log`.

## Data, privacy and safety

The upstream globe retrieves public geospatial data and third-party imagery.
The source-code license does not automatically cover every dataset, tile,
camera feed, map, or 3D asset. Review the upstream
[DATA_SOURCES.md](https://github.com/bilawalsidhu/gods-eye-view/blob/main/DATA_SOURCES.md)
and [SECURITY.md](https://github.com/bilawalsidhu/gods-eye-view/blob/main/SECURITY.md)
before redistribution or use. Configure provider keys locally; never commit
secrets. HOMER keeps the service on loopback and does not expose it to a LAN.

This is a public-data visualization workspace, not a navigation, emergency
response, or operational targeting system. Do not use it to identify or track
private individuals.

## Upstream

https://github.com/bilawalsidhu/gods-eye-view
