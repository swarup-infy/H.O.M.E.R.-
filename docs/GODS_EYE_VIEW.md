# God's Eye View integration notes

HOMER exposes a **God's Eye View** workspace launcher in the desktop sidebar. It opens a separately installed local globe service in the system browser. The default URL is `http://127.0.0.1:4173`; override it with `HOMER_GLOBE_URL` in the local `.env` file. The launcher accepts localhost URLs only.

## Install the upstream globe separately

The upstream project is a standalone JavaScript/Cesium application, not a Python package or a drop-in PySide6 widget. Keep it in a sibling folder rather than copying its large source tree into HOMER:

```powershell
cd D:\Software
git clone https://github.com/bilawalsidhu/gods-eye-view.git
cd gods-eye-view
npm ci
npm run doctor
npm run dev
```

Open HOMER and choose **God's Eye View** from the sidebar. Start the globe service first. The upstream project documents Node.js 24.14+ (24.x) or 26.x and serves the local app on port 4173 by default. Use a normal hardware-accelerated browser if an embedded browser view is slow.

## Planned HOMER integration phases

1. Launch and status-check the local globe service.
2. Add an explicit bridge between HOMER voice commands and a narrow set of map actions (search a place, reset globe, toggle approved layers, track a public asset).
3. Add a curated layer selector and metadata cards.
4. Consider deeper native embedding only after desktop performance and browser-engine support are measured.

## Important limitations and safety

- HOMER's Groq chat API remains hosted; this feature does not add a local LLM.
- The upstream app's code is MIT-licensed. Third-party datasets, camera feeds, 3D models, imagery and API providers have separate terms. Review upstream `DATA_SOURCES.md`, `SECURITY.md` and asset-specific licenses before redistributing or using them.
- Do not commit API keys or access tokens. Configure provider keys locally in the globe app.
- Keep the local globe bound to loopback. Do not expose it to a LAN or public network without reviewing its security model.
- This is exploratory public-data visualization, not navigation, emergency response, or an operational targeting system. Do not use it to identify or track private individuals.

## References

- Upstream: https://github.com/bilawalsidhu/gods-eye-view
- Upstream data-source and license notes: https://github.com/bilawalsidhu/gods-eye-view/blob/main/DATA_SOURCES.md
- Upstream security notes: https://github.com/bilawalsidhu/gods-eye-view/blob/main/SECURITY.md
