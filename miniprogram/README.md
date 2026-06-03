# DocFormatConverter — Mini Program (WeChat / H5 / Alipay)

Taro 3 + React. One codebase, three platforms.

Built it because half of our users only have a phone. The web app is
fine for desktop, but downloading a converted file from a website on
a phone is painful. This lets them just hit "save" in WeChat.

## Build

```bash
npm install

# WeChat (open the dist/ folder in WeChat DevTools)
npm run dev:weapp

# H5 — runs at http://localhost:10086
npm run dev:h5

# Production builds land in dist/
npm run build:weapp
npm run build:h5
```

The default API base is `http://localhost:8000/api`. Override with
`TARO_APP_API_BASE` in `.env`.

## What's here

- 7 pages: index, login, register, convert, tasks, task-detail, profile
- Custom tab bar (no PNG assets — uses emoji, keeps the bundle tiny)
- `useAuth()` hook with global state + listener fan-out (no Redux/Zustand;
  the mini-program runtime is too constrained to justify it here)
- Double-token auto-refresh in `api/client.ts`

## What's not here yet

- WebSocket progress on the task-detail page. The store has a `subscribe`
  method, the client has a `Taro.connectSocket` call commented out, but
  I never wired up the reconnect/backoff properly. For now we poll every
  3s, which is fine for a 5-second conversion but jittery on PDFs.
  Branch: `feature/mp-ws`.

- i18n. Pages are hardcoded in Chinese. WeChat users in our context
  are Chinese, so the priority is low.

- Real avatar upload. The profile page shows the first letter of your
  email as a fallback, which actually looks fine.

## Conventions

- Each page is a directory: `pages/convert/` contains `index.tsx`,
  `index.config.ts`, and a colocated `.scss` file. Don't put styles
  in a shared file — Taro's class scoping is per-file and mixing them
  causes grief.
- All Taro API calls go through `api/client.ts`. Never call `Taro.request`
  directly from a page; it bypasses the token-refresh middleware.
- Path alias `@/` → `src/`. Configured in `tsconfig.json` and
  `config/index.ts`.
