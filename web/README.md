# Graph Review UI - Frontend

React + TypeScript frontend for the Graph Modification Review interface.

## Features

- 📊 Proposal review interface with collapsible cards
- 💬 Chat interface with AI agent
- ✏️ Inline editing of proposed changes
- 🔍 Evidence panels with confidence scores
- 🎨 Dark theme optimized for long sessions
- ⚡ Fast rendering with React 18

## Tech Stack

- React 18
- TypeScript
- Vite
- Tailwind CSS

## Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
src/
├── components/
│   └── GraphReview/
│       ├── index.tsx           # Main container
│       ├── ProposalCard.tsx    # Proposal display
│       ├── ChangeItem.tsx      # Individual change
│       ├── ChangeEditor.tsx    # Inline editor
│       ├── EvidencePanel.tsx   # Evidence display
│       ├── ChatPanel.tsx       # Chat interface
│       └── QuickActions.tsx    # Quick action buttons
├── hooks/
│   └── useGraphReview.ts       # State management
├── types/
│   └── graph.ts                # TypeScript types
├── utils/
│   └── agentMock.ts            # Mock data (dev)
├── App.tsx
├── main.tsx
└── index.css
```

## Configuration

Edit `vite.config.ts` to change backend URL:

```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

## Environment Variables

Create `.env.local`:

```bash
VITE_API_URL=http://localhost:8000
```

## Building

```bash
npm run build
```

Output in `dist/` directory.

## License

Apache 2.0
