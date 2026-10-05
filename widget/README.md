# Embeddable Chat Widget

Vanilla JS snippet (~150 lines, zero dependencies) that adds a floating chat
bubble to any website. Clicking the bubble opens a `380×600` iframe pointing at
your hosted agent page.

## Copy-paste snippet

```html
<script
  src="https://your-frontend-host/widget.js"
  data-agent="demo-bakery"
  data-api="https://your-api-host"
  data-base="https://your-frontend-host"
></script>
```

For local development:

```html
<script
  src="http://localhost:3000/widget.js"
  data-agent="demo-bakery"
  data-api="http://localhost:8000"
  data-base="http://localhost:3000"
></script>
```

## Attributes

| Attribute    | Required | Default                 | Description                                      |
| ------------ | -------- | ----------------------- | ------------------------------------------------ |
| `data-agent` | yes      | —                       | Agent slug, e.g. `demo-bakery`.                  |
| `data-api`   | no       | `http://localhost:8000` | Backend API base, used to fetch the brand colour.|
| `data-base`  | no       | `http://localhost:3000` | Frontend base; iframe loads `{base}/c/{slug}?embed=true`. |

## Behaviour

- Floating bubble: 60px circle, bottom-right, `z-index 2147483000`.
- Bubble colour: agent `primaryColor` fetched from `{api}/api/agents/{slug}`
  (falls back to `{api}/agents/{slug}`, then `#10b981`).
- Click toggles a `380×600` panel (`max-width: 100vw - 32px`); `Esc` closes it.
- Iframe `src` is set lazily on first open so the embed costs nothing until used.
- Mobile responsive: below 480px the panel becomes full-width (`70vh` tall).
- Multiple widgets with different slugs can coexist (DOM ids are slug-scoped).

## Local demo

```bash
cd widget
python3 -m http.server 5500
# open http://localhost:5500/test.html
```

Requires the backend on `:8000` and frontend on `:3000` for the iframe and
brand-colour fetch to resolve.
