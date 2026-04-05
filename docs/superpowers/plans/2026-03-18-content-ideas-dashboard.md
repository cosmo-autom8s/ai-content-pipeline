# Content Ideas Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only desktop dashboard for viewing Content Ideas from Notion, with a card grid and slide-out detail panel.

**Architecture:** FastAPI backend (port 8088) proxies Notion API and serves the built React app. Vite + React frontend with styled-components for theming. Centralized dark-mode theme in `theme.js`. All files live under `frontend/` and `api/` within the existing `content-pipeline-bot/` project.

**Tech Stack:** Python 3.9+ / FastAPI / uvicorn / httpx, Node.js / Vite / React / styled-components

**Spec:** `docs/superpowers/specs/2026-03-18-content-ideas-dashboard-design.md`

---

## File Map

### New Files — API (`api/`)

| File | Responsibility |
|------|---------------|
| `api/__init__.py` | Empty — makes `api/` a Python package for `import api.notion` |
| `api/requirements.txt` | Python deps: fastapi, uvicorn, httpx, python-dotenv |
| `api/server.py` | FastAPI app: 3 endpoints + static file serving |
| `api/notion.py` | Notion API client: query, get page, parse properties |
| `api/test_server.py` | API endpoint tests |

### New Files — Frontend (`frontend/`)

| File | Responsibility |
|------|---------------|
| `frontend/package.json` | Node deps + scripts |
| `frontend/vite.config.js` | Vite config with `/api` proxy |
| `frontend/index.html` | HTML shell |
| `frontend/src/main.jsx` | Entry point, ThemeProvider |
| `frontend/src/App.jsx` | Main app, state management, layout composition |
| `frontend/src/theme/theme.js` | All design tokens |
| `frontend/src/theme/GlobalStyles.jsx` | CSS reset + global styles |
| `frontend/src/components/Layout.jsx` | Page shell: header, stats, grid container |
| `frontend/src/components/IdeaCard.jsx` | Card tile in grid |
| `frontend/src/components/IdeaDetail.jsx` | Slide-out detail panel |
| `frontend/src/components/FilterBar.jsx` | Sort/filter controls |
| `frontend/src/hooks/useIdeas.js` | Data fetching, filtering, sorting state |

### Helper

| File | Responsibility |
|------|---------------|
| `run.sh` | Convenience script: build frontend + start API server |

---

## Task 0: Project Setup — Git Init & .gitignore

**Files:**
- Create: `.gitignore`

### Step 0.1: Initialize git repo

- [ ] **Create `.gitignore`**

```
# Python
venv/
__pycache__/
*.pyc
*.pyo
.env

# Frontend
frontend/node_modules/
frontend/dist/

# OS
.DS_Store

# IDE
.idea/
.vscode/
```

- [ ] **Initialize git and make initial commit**

```bash
cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot
git init
git add .gitignore
git commit -m "chore: initialize git repo with .gitignore"
```

---

## Task 1: API — Python Backend

**Files:**
- Create: `api/requirements.txt`
- Create: `api/notion.py`
- Create: `api/server.py`
- Create: `api/test_server.py`
- Reference: `.env` (existing — has `NOTION_API_KEY`, `NOTION_IDEAS_DB_ID`)
- Reference: `engines/ideation.py` (existing — has Notion property extraction patterns)

### Step 1.1: Create API requirements

- [ ] **Create `api/__init__.py`** — empty file, makes `api/` importable as a Python package.

- [ ] **Create `api/requirements.txt`**

```
fastapi>=0.104.0
uvicorn>=0.24.0
httpx>=0.25.0
python-dotenv>=1.0.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
httpx[http2]>=0.25.0
```

- [ ] **Install deps**

Run: `cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot && source venv/bin/activate && pip install -r api/requirements.txt`

- [ ] **Commit**

```bash
git add api/__init__.py api/requirements.txt
git commit -m "feat(api): add Python dependencies for FastAPI backend"
```

### Step 1.2: Create Notion client

- [ ] **Create `api/notion.py`** — Notion API client that queries the Content Ideas DB and parses properties into clean dicts.

The module should:
1. Load `NOTION_API_KEY` and `NOTION_IDEAS_DB_ID` from `.env` (using `python-dotenv`, path relative to project root like `engines/ideation.py` does)
2. Use `httpx.AsyncClient` for async HTTP to Notion API
3. Use Notion API version `2022-06-28` (same as existing code)
4. Implement these functions:

```python
async def query_all_ideas() -> list[dict]:
    """Query Content Ideas DB, handling Notion pagination (100 per page).
    Returns list of idea dicts with list-level fields:
    id, name, score, top_pick, status, main_topic, format,
    filming_setup (list), filming_priority, frame_type (list),
    topic_cluster, urgency, description
    """

async def get_idea_detail(page_id: str) -> dict:
    """Get a single idea page with ALL fields including hooks, captions, etc.
    Returns full idea dict with all list-level fields PLUS:
    angle, reasoning, hook_1-hook_5, original_url,
    source_link ({name, url}), filmed_date, posted_date,
    caption_tiktok, caption_instagram, caption_youtube, caption_linkedin,
    post_urls (list of strings)
    """

async def get_ideas_stats() -> dict:
    """Return { total, by_status: {new: N, ...}, top_picks: N }"""
```

Property extraction helpers (follow patterns from `engines/ideation.py:48-64`):
- `_get_text(props, key)` — rich_text or title → string
- `_get_select(props, key)` — select → string or None
- `_get_status(props, key)` — status → string or None. **Important:** Notion's "status" type returns `{"status": {"name": "..."}}`, NOT `{"select": {...}}`. The Status field on Content Ideas uses this type.
- `_get_multi_select(props, key)` — multi_select → list of strings
- `_get_number(props, key)` — number → float or None
- `_get_checkbox(props, key)` — checkbox → bool
- `_get_url(props, key)` — url → string or None
- `_get_date(props, key)` — date → ISO string or None
- `_get_relation(props, key)` — relation → list of page IDs
- `_parse_post_urls(text)` — split newline-separated text into list of URL strings

For `source_link` resolution in `get_idea_detail`: if the relation field has a page ID, make a second Notion API call to get that page's title and construct its Notion URL (`https://notion.so/{page_id_without_hyphens}`).

- [ ] **Commit**

```bash
git add api/notion.py
git commit -m "feat(api): add Notion API client with query, detail, and stats functions"
```

### Step 1.3: Create FastAPI server

- [ ] **Create `api/server.py`** — FastAPI app with 3 API endpoints + static file serving.

```python
# Key structure:
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import api.notion as notion

app = FastAPI()

# --- API routes (registered BEFORE static files) ---

@app.get("/api/stats")  # BEFORE /api/ideas/{id} to avoid route conflict
async def get_stats():
    return await notion.get_ideas_stats()

@app.get("/api/ideas")
async def list_ideas(
    status: str | None = None,        # comma-separated
    sort: str = "score",              # score, name, status, urgency
    order: str = "desc",              # asc, desc
    filming_setup: str | None = None,
    format: str | None = None,
    top_pick: str | None = None,      # "true"
    search: str | None = None,        # case-insensitive contains
):
    ideas = await notion.query_all_ideas()
    # Apply filters in Python (Notion API filtering is limited for complex queries)
    # 1. status filter (comma-separated → set lookup)
    # 2. filming_setup filter
    # 3. format filter
    # 4. top_pick filter
    # 5. search filter (case-insensitive on name, main_topic, description)
    # 6. sort
    # 7. return
    return ideas

@app.get("/api/ideas/{idea_id}")
async def get_idea(idea_id: str):
    return await notion.get_idea_detail(idea_id)

# --- Static file serving (built React app) ---
# Only mount if the build directory exists
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve index.html for all non-API routes (SPA fallback)."""
        return FileResponse(frontend_dist / "index.html")
```

Important implementation details:
- Use `from __future__ import annotations` for Python 3.9 compat (matching existing codebase pattern)
- Filtering and sorting happen in Python after fetching from Notion — this is simpler and more flexible than Notion's filter API for complex multi-field queries
- The SPA catch-all route must be registered LAST, after API routes and static assets
- CORS middleware is NOT needed — same origin in production, Vite proxy in dev

- [ ] **Commit**

```bash
git add api/server.py
git commit -m "feat(api): add FastAPI server with ideas endpoints and static serving"
```

### Step 1.4: Test the API

- [ ] **Create `api/test_server.py`** — tests for the API endpoints using FastAPI's TestClient.

Test cases:
1. `GET /api/ideas` returns a list
2. `GET /api/ideas?status=new` filters correctly
3. `GET /api/ideas?status=new,queued` multi-status filter works
4. `GET /api/ideas?sort=score&order=desc` returns sorted results
5. `GET /api/ideas?search=something` filters by text
6. `GET /api/ideas?top_pick=true` filters top picks
7. `GET /api/ideas/{valid_id}` returns full detail with hooks
8. `GET /api/ideas/{invalid_id}` returns 404
9. `GET /api/stats` returns correct shape with total, by_status, top_picks

Note: These tests hit the real Notion API (this is a personal tool, not CI). They verify the full integration works. Run with the venv active so `.env` is loaded.

```bash
cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot
source venv/bin/activate
python -m pytest api/test_server.py -v
```

- [ ] **Verify API manually**

```bash
cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot
source venv/bin/activate
uvicorn api.server:app --port 8088 &
# Test endpoints:
curl http://localhost:8088/api/stats | python -m json.tool
curl http://localhost:8088/api/ideas | python -m json.tool | head -50
# Kill the server:
kill %1
```

- [ ] **Commit**

```bash
git add api/test_server.py
git commit -m "test(api): add integration tests for ideas API endpoints"
```

---

## Task 2: Frontend — Scaffold & Theme

**Files:**
- Create: `frontend/` (Vite scaffold)
- Create: `frontend/src/theme/theme.js`
- Create: `frontend/src/theme/GlobalStyles.jsx`
- Modify: `frontend/src/main.jsx` (add ThemeProvider)
- Modify: `frontend/vite.config.js` (add proxy)

### Step 2.1: Scaffold Vite + React project

- [ ] **Create Vite project**

```bash
cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install styled-components
```

- [ ] **Configure Vite proxy**

Replace `frontend/vite.config.js` with:

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8088',
    },
  },
})
```

- [ ] **Clean up scaffold** — Remove default Vite boilerplate:
  - Delete `frontend/src/App.css`
  - Delete `frontend/src/index.css`
  - Delete `frontend/src/assets/react.svg`
  - Delete `frontend/public/vite.svg`
  - Remove CSS imports from `main.jsx` and `App.jsx`

- [ ] **Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Vite + React project with styled-components"
```

### Step 2.2: Create theme and global styles

- [ ] **Create `frontend/src/theme/theme.js`** — Copy the exact theme object from the spec (lines 188-249 of the design spec). Export as `export const theme = { ... }`.

- [ ] **Create `frontend/src/theme/GlobalStyles.jsx`**

```jsx
import { createGlobalStyle } from 'styled-components'

const GlobalStyles = createGlobalStyle`
  *, *::before, *::after {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  html, body, #root {
    height: 100%;
    background: ${({ theme }) => theme.colors.bg};
    color: ${({ theme }) => theme.colors.text};
    font-family: ${({ theme }) => theme.fonts.body};
    font-size: ${({ theme }) => theme.fontSize.md};
    -webkit-font-smoothing: antialiased;
  }

  a {
    color: ${({ theme }) => theme.colors.accent};
    text-decoration: none;
    &:hover { color: ${({ theme }) => theme.colors.accentHover}; }
  }
`

export default GlobalStyles
```

- [ ] **Update `frontend/src/main.jsx`** — Wrap app in ThemeProvider:

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { ThemeProvider } from 'styled-components'
import { theme } from './theme/theme'
import GlobalStyles from './theme/GlobalStyles'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <GlobalStyles />
      <App />
    </ThemeProvider>
  </React.StrictMode>,
)
```

- [ ] **Update `frontend/src/App.jsx`** — Minimal placeholder:

```jsx
function App() {
  return <div>Content Ideas Dashboard</div>
}

export default App
```

- [ ] **Verify** — Start both servers and confirm the dark background renders:

```bash
# Terminal 1:
cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot && source venv/bin/activate && uvicorn api.server:app --port 8088

# Terminal 2:
cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot/frontend && npm run dev
```

Open `http://localhost:5173` — should show "Content Ideas Dashboard" on a dark `#0f1117` background.

- [ ] **Commit**

```bash
git add frontend/src/theme/ frontend/src/main.jsx frontend/src/App.jsx
git commit -m "feat(frontend): add dark mode theme system with GlobalStyles and ThemeProvider"
```

---

## Task 3: Frontend — Data Layer

**Files:**
- Create: `frontend/src/hooks/useIdeas.js`

### Step 3.1: Create the useIdeas hook

- [ ] **Create `frontend/src/hooks/useIdeas.js`**

This hook manages all data fetching and client-side state:

```js
// State it manages:
// - ideas: array from /api/ideas
// - selectedIdea: full detail from /api/ideas/{id} (null when panel closed)
// - stats: object from /api/stats
// - loading: boolean
// - error: string or null
// - filters: { status, sort, order, filming_setup, format, top_pick, search }

// Functions it exposes:
// - fetchIdeas() — calls GET /api/ideas with current filters as query params
// - selectIdea(id) — calls GET /api/ideas/{id}, sets selectedIdea
// - closeDetail() — sets selectedIdea to null
// - updateFilters(newFilters) — merges into filters, triggers fetchIdeas
// - fetchStats() — calls GET /api/stats

// Behavior:
// - fetchIdeas runs on mount and whenever filters change
// - fetchStats runs on mount
// - All fetches use native fetch() — no axios needed
// - Error handling: set error state, keep stale data visible
```

- [ ] **Verify** — Temporarily wire into App.jsx to confirm data loads:

```jsx
// In App.jsx, temporarily:
import { useIdeas } from './hooks/useIdeas'

function App() {
  const { ideas, stats, loading, error } = useIdeas()
  if (loading) return <div>Loading...</div>
  if (error) return <div>Error: {error}</div>
  return <div>{stats?.total} ideas loaded. First: {ideas[0]?.name}</div>
}
```

Confirm data loads from Notion via the API at `http://localhost:5173`.

- [ ] **Commit**

```bash
git add frontend/src/hooks/useIdeas.js frontend/src/App.jsx
git commit -m "feat(frontend): add useIdeas hook for data fetching and filter state"
```

---

## Task 4: Frontend — Layout & IdeaCard

**Files:**
- Create: `frontend/src/components/Layout.jsx`
- Create: `frontend/src/components/IdeaCard.jsx`
- Modify: `frontend/src/App.jsx`

Use `frontend-design` skill for component implementation (agent skill hint — provides component structure, styling, and responsive layout guidance).

### Step 4.1: Create Layout component

- [ ] **Create `frontend/src/components/Layout.jsx`**

Page shell with:
- Fixed header bar with app name "Content Ideas" and stats summary ("47 ideas, 5 top picks")
- Grid container below using CSS Grid: `grid-template-columns: repeat(3, 1fr)` with `gap` from theme. Add `@media (max-width: 1200px)` breakpoint to switch to `repeat(2, 1fr)`.
- All spacing/colors from theme via styled-components

Props: `{ stats, children }`

### Step 4.2: Create IdeaCard component

- [ ] **Create `frontend/src/components/IdeaCard.jsx`**

Card tile showing (per spec):
- Score — large color-coded number. Use `theme.colors.score.high/mid/low` based on value (>=8 green, >=6 yellow, <6 red)
- Name — truncated with CSS `text-overflow: ellipsis` if needed
- Top Pick — small badge if `top_pick === true`
- Main Topic — text label
- Format — pill/tag using `theme.colors.accent`
- Filming Setup — array of small tags
- Status — colored pill using `theme.colors.status[status]`
- Filming Priority — color indicator using `theme.colors.filmingPriority[priority]`

Props: `{ idea, onClick }`

The card should have `cursor: pointer`, `theme.shadows.card` shadow, `theme.colors.surface` background, `theme.colors.surfaceHover` on hover, `theme.radius.md` border radius.

### Step 4.3: Wire into App

- [ ] **Update `frontend/src/App.jsx`** to compose Layout + IdeaCard grid:

```jsx
// Rough structure:
function App() {
  const { ideas, stats, loading, error, selectIdea } = useIdeas()

  return (
    <Layout stats={stats}>
      {loading && <Spinner />}  {/* simple CSS spinner */}
      {error && <ErrorBanner message={error} />}
      <CardGrid>
        {ideas.map(idea => (
          <IdeaCard key={idea.id} idea={idea} onClick={() => selectIdea(idea.id)} />
        ))}
      </CardGrid>
      {ideas.length === 0 && !loading && <EmptyState />}
    </Layout>
  )
}
```

- [ ] **Verify** — Open `http://localhost:5173`, confirm card grid renders with real Notion data, dark theme, color-coded scores.

- [ ] **Commit**

```bash
git add frontend/src/components/Layout.jsx frontend/src/components/IdeaCard.jsx frontend/src/App.jsx
git commit -m "feat(frontend): add Layout and IdeaCard components with themed card grid"
```

---

## Task 5: Frontend — IdeaDetail Slide-Out Panel

**Files:**
- Create: `frontend/src/components/IdeaDetail.jsx`
- Modify: `frontend/src/App.jsx`

Use `frontend-design` skill for component implementation (agent skill hint — provides component structure, styling, and responsive layout guidance).

### Step 5.1: Create IdeaDetail component

- [ ] **Create `frontend/src/components/IdeaDetail.jsx`**

Slide-out panel (per spec):
- Slides in from right, ~40-50% screen width
- Overlay behind it dims the grid (`theme.colors.overlay`)
- Close via X button (top right) or clicking overlay
- CSS transition for smooth slide-in (`transform: translateX`)

Sections (all using theme tokens for spacing/colors):

1. **Header** — Name (large), Score (big color-coded number), Top Pick badge, Status pill
2. **Hooks** — Most important section. Numbered list of Hook 1-5 with clear visual hierarchy. Use slightly larger font, good spacing between hooks.
3. **Overview** — Description, Angle, Main Topic, Format, Urgency
4. **Reasoning** — Creative director scoring rationale (use `theme.fonts.mono` or a distinct style)
5. **Filming** — Filming Setup tags, Filming Priority (color-coded), Frame Type tags
6. **Meta** — Topic Cluster, Original URL (clickable `<a>` tag), Source Link (name + clickable link)
7. **Captions** (conditional — only render if any caption exists) — TikTok, Instagram, YouTube, LinkedIn. Each in a labeled block with `theme.fonts.mono` for the caption text.
8. **Dates** (conditional) — filmed_date, posted_date, post URLs (list of clickable links)

Props: `{ idea, onClose }` — `idea` is the full detail object from `GET /api/ideas/{id}`, `onClose` closes the panel.

### Step 5.2: Wire into App

- [ ] **Update `frontend/src/App.jsx`** — Add IdeaDetail panel:

```jsx
// Add to App:
{selectedIdea && (
  <IdeaDetail idea={selectedIdea} onClose={closeDetail} />
)}
```

- [ ] **Verify** — Click a card in the grid, confirm panel slides in from right with full detail. Click overlay or X to close.

- [ ] **Commit**

```bash
git add frontend/src/components/IdeaDetail.jsx frontend/src/App.jsx
git commit -m "feat(frontend): add slide-out detail panel with hooks, scoring, and captions"
```

---

## Task 6: Frontend — FilterBar

**Files:**
- Create: `frontend/src/components/FilterBar.jsx`
- Modify: `frontend/src/App.jsx`

Use `frontend-design` skill for component implementation (agent skill hint — provides component structure, styling, and responsive layout guidance).

### Step 6.1: Create FilterBar component

- [ ] **Create `frontend/src/components/FilterBar.jsx`**

Horizontal bar at top of page (below header, above grid):

1. **Sort by** — styled `<select>` dropdown. Options: Score (default), Name, Status, Urgency. Changing triggers `updateFilters({ sort: value })`.
2. **Sort order** — toggle button (asc/desc arrow icon or text)
3. **Status pills** — clickable pills for each status (new, queued, filming_today, filmed, captioned, posted, archived). Multiple can be active. Active pills use `theme.colors.status[status]` as background. Clicking toggles. Updates `filters.status` as comma-separated string.
4. **Filming Setup** — multi-select (same pill pattern as status)
5. **Format** — `<select>` dropdown (values populated from loaded ideas)
6. **Top Picks only** — toggle/checkbox
7. **Search** — text `<input>` with debounce (~300ms). Styled with `theme.colors.surface` background, `theme.colors.border` border.
8. **Clear filters** — small "clear" button, resets all to defaults

Props: `{ filters, onFilterChange }` — `onFilterChange` receives partial filter updates.

### Step 6.2: Wire into App

- [ ] **Update `frontend/src/App.jsx`** — Add FilterBar between header and grid:

```jsx
<Layout stats={stats}>
  <FilterBar filters={filters} onFilterChange={updateFilters} />
  <CardGrid>
    {ideas.map(idea => (
      <IdeaCard key={idea.id} idea={idea} onClick={() => selectIdea(idea.id)} />
    ))}
  </CardGrid>
</Layout>
```

- [ ] **Verify** — Test each filter: status pills toggle, sort changes order, search narrows results, clear resets everything.

- [ ] **Commit**

```bash
git add frontend/src/components/FilterBar.jsx frontend/src/App.jsx
git commit -m "feat(frontend): add FilterBar with sort, status pills, search, and format filters"
```

---

## Task 7: Production Serving & Convenience Script

**Files:**
- Create: `run.sh`
- Modify: `frontend/index.html` (title)

### Step 7.1: Set HTML title

- [ ] **Update `frontend/index.html`** — Change `<title>` to "Content Ideas — Autom8Lab"

### Step 7.2: Create run script

- [ ] **Create `run.sh`** at project root:

```bash
#!/bin/bash
# Build frontend and start the dashboard server on port 8088

set -e

cd "$(dirname "$0")"

echo "Building frontend..."
cd frontend && npm run build && cd ..

echo "Starting server on http://localhost:8088"
source venv/bin/activate
uvicorn api.server:app --port 8088 --host 0.0.0.0
```

```bash
chmod +x run.sh
```

### Step 7.3: Build and verify production mode

- [ ] **Build and test**

```bash
cd /Users/cosmo/Documents/AIProjects/content-pipeline-bot
./run.sh
```

Open `http://localhost:8088` — should serve the full dashboard (React app + API) from a single port.

- [ ] **Commit**

```bash
git add run.sh frontend/index.html
git commit -m "feat: add run.sh for single-command dashboard startup"
```

---

## Task 8: Final Review & Cleanup

### Step 8.1: End-to-end walkthrough

- [ ] **Full flow test:**
  1. Start with `./run.sh`
  2. Open `http://localhost:8088`
  3. Verify card grid loads with real Notion data
  4. Verify scores are color-coded correctly
  5. Verify top pick badges show
  6. Click a card → detail panel slides in
  7. Verify all 5 hooks display
  8. Verify captions section shows (if data exists)
  9. Close panel via X and via overlay click
  10. Test each filter: status pills, sort dropdown, search, top picks toggle
  11. Test "clear filters" resets everything
  12. Verify stats in header are accurate

### Step 8.2: Clean up and final commit

- [ ] **Remove any temporary debug code** from App.jsx or other files

- [ ] **Final commit**

```bash
git add -A
git commit -m "feat: Content Ideas Dashboard v1 — read-only card grid with detail panel"
```
