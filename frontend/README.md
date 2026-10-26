# ORBIT Mission Control - Frontend

A modern, dark-themed mission control dashboard for the ORBIT autonomous research platform. Built with React 18, TypeScript, Vite, and Tailwind CSS.

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.example .env

# Start development server
npm run dev
```

The app will be available at `http://localhost:5173` with API proxy to `http://127.0.0.1:8000`.

## 📁 Project Structure

```
frontend/
├── public/
│   └── orbit-icon.svg           # App favicon
├── src/
│   ├── api/
│   │   └── client.ts            # Axios API client with typed endpoints
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.tsx     # Main layout with sidebar + topbar
│   │   │   ├── Sidebar.tsx      # Collapsible navigation sidebar
│   │   │   └── Topbar.tsx       # Top navigation with breadcrumbs
│   │   └── ui/                  # Reusable UI components
│   │       ├── Button.tsx
│   │       ├── Input.tsx
│   │       ├── Card.tsx
│   │       ├── Badge.tsx
│   │       ├── Modal.tsx
│   │       └── Tabs.tsx
│   ├── hooks/
│   │   ├── useMissionWebSocket.ts  # WebSocket connection hook
│   │   └── useTheme.ts             # Theme management hook
│   ├── pages/
│   │   ├── Overview.tsx       # Mission Control dashboard
│   │   ├── Missions.tsx       # Mission list & creation
│   │   ├── MissionDetail.tsx  # Mission detail with tabs
│   │   ├── Hypotheses.tsx     # Hypothesis management
│   │   ├── Experiments.tsx    # Experiment registry
│   │   ├── ExperimentDetail.tsx # Experiment detail with charts
│   │   ├── Registry.tsx       # Model registry & champion
│   │   ├── Live.tsx           # Real-time WebSocket monitoring
│   │   ├── Research.tsx       # Evidence cards library
│   │   └── Settings.tsx       # User & app settings
│   ├── stores/
│   │   └── useOrbitStore.ts   # Zustand global state store
│   ├── styles/
│   │   └── globals.css        # Tailwind + custom styles
│   ├── types/
│   │   └── api.ts             # TypeScript API types
│   ├── App.tsx                # Route definitions
│   ├── main.tsx               # Entry point
│   └── vite-env.d.ts          # Vite type declarations
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
└── .env.example
```

## 🎨 Design System

### Color Palette (CSS Variables)

```css
/* Backgrounds */
--orbit-bg-primary: #030712      /* Near-black */
--orbit-bg-secondary: #0c1222    /* Dark blue-grey */
--orbit-bg-tertiary: #111827     /* Elevated surfaces */
--orbit-bg-card: #0f172a         /* Card backgrounds */

/* Borders */
--orbit-border-primary: #1e293b  /* Subtle */
--orbit-border-secondary: #334155 /* Stronger */
--orbit-border-focus: #06b6d4    /* Electric cyan */

/* Accents */
--orbit-accent-primary: #06b6d4  /* Electric cyan */
--orbit-accent-secondary: #a855f7 /* Restrained violet */
--orbit-accent-positive: #22c55e  /* Controlled green */
--orbit-accent-warning: #f59e0b   /* Amber */
--orbit-accent-negative: #ef4444  /* Restrained red */

/* Text */
--orbit-text-primary: #f8fafc    /* Near white */
--orbit-text-secondary: #94a3b8  /* Muted */
--orbit-text-tertiary: #64748b   /* Subtle */
```

### Agent Colors
- **Researcher**: Cyan (`#06b6d4`)
- **Hypothesizer**: Violet (`#a855f7`)
- **Skeptic**: Amber (`#f59e0b`)
- **Experimenter**: Green (`#22c55e`)
- **Evaluator**: Red (`#ef4444`)
- **Orchestrator**: Pink (`#ec4899`)

### Typography
- **Sans**: Inter (UI text)
- **Mono**: JetBrains Mono (code, IDs, metrics)

### Spacing Scale
Based on 4px base unit with semantic naming.

## 🔌 API Integration

The `apiClient` in `src/api/client.ts` provides typed methods for all backend endpoints:

- **Missions**: `createMission`, `listMissions`, `getMission`, `updateMission`
- **Hypotheses**: `createHypothesis`, `listHypotheses`, `getHypothesis`, `updateHypothesis`
- **Experiments**: `createExperiment`, `listExperiments`, `getExperiment`, `getChampion`, `promoteExperiment`
- **WebSocket**: `broadcastEvent`, `getWSStats`

All methods return typed responses matching backend Pydantic schemas.

## 🔄 Real-time Features

The `useMissionWebSocket` hook provides:
- Automatic connection management with exponential backoff reconnection
- Heartbeat/ping for connection health
- Message parsing and routing to Zustand store
- Event types: `agent_message`, `run_progress`, `run_metrics`, `verdict`, `system`

## 📊 State Management

Zustand store (`useOrbitStore`) manages:
- Missions, hypotheses, experiments lists and detail views
- WebSocket messages, run progress, metrics, verdicts, system messages
- UI state: sidebar collapse, theme, active mission context
- Persisted preferences (sidebar, theme) in localStorage

## 🧪 Available Scripts

```bash
npm run dev          # Start dev server
npm run build        # Type-check + production build
npm run preview      # Preview production build
npm run lint         # ESLint with TypeScript
npm run typecheck    # TypeScript compilation check
npm run test         # Run Vitest tests
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | REST API base URL |
| `VITE_WS_BASE_URL` | `ws://127.0.0.1:8000` | WebSocket base URL |

### Tailwind Customization

Edit `tailwind.config.js` to customize:
- Color palette (CSS variables in `globals.css`)
- Typography scale
- Spacing, border radius, shadows
- Custom animations

## 📱 Responsive Breakpoints

- **Mobile**: < 640px (stacked layout, collapsible sidebar)
- **Tablet**: 640px - 1024px (sidebar overlay)
- **Desktop**: > 1024px (permanent sidebar)
- **Wide**: > 1280px (expanded content area)

## ♿ Accessibility

- Semantic HTML5 elements
- ARIA labels and roles on interactive components
- Focus management in modals and tabs
- Keyboard navigation support
- Color contrast ratios (WCAG AA)
- Reduced motion support

## 🧩 Adding New Pages

1. Create page component in `src/pages/`
2. Add route in `src/App.tsx`
3. Add navigation item in `src/components/layout/Sidebar.tsx`
4. Update breadcrumbs in `src/components/layout/Topbar.tsx` if needed

## 📦 Key Dependencies

| Package | Purpose |
|---------|---------|
| `react-router-dom` | Client-side routing |
| `axios` | HTTP client |
| `zustand` | Global state |
| `recharts` | Data visualization |
| `lucide-react` | Icons |
| `sonner` | Toast notifications |
| `react-hook-form` + `zod` | Form validation |
| `date-fns` | Date formatting |

## 🔒 Type Safety

- Strict TypeScript configuration
- API types generated from backend schemas
- Zod validation for all forms
- Path aliases (`@/*` → `src/*`)

## 🚀 Production Deployment

```bash
npm run build
# Output in dist/
# Serve with nginx, Vercel, Netlify, etc.
```

Ensure environment variables are set in production:
- `VITE_API_BASE_URL=https://api.yourdomain.com`
- `VITE_WS_BASE_URL=wss://api.yourdomain.com`

## 📄 License

Part of the ORBIT platform. See root LICENSE file.