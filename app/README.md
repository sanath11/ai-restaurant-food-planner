# Restaurant Planner App

Flask-based web app following reference dashboard pattern with HTML templates.

## Structure

```
app/
├── app.py              # Flask app with API endpoints
├── app.yaml            # App configuration
├── requirements.txt    # Dependencies (Flask, psycopg2, requests)
├── templates/          # HTML templates
│   └── index.html      # Main dashboard UI
├── yelp_adapter.py     # Yelp API client
├── weather_adapter.py  # Weather API client
└── lakebase.py         # Lakebase Postgres connection helper
```

## Design Patterns

Following **databricks-app-design** skill:

### Composition
- **Genre**: Analytic dashboard with search
- **Data abstraction**: KPI cards (total, avg rating, favorites, weather) + restaurant cards grid
- **Layout**: Responsive grid (auto-fit columns)
- **Interaction**: Live search with loading/empty/error states
- **Color**: Databricks semantic tokens (--db-blue, --db-green, etc.)

### Notation
- **Message-in-title**: KPI cards show label + value + context
- **Semantic color**: 
  - Blue (info/primary) for restaurants count
  - Orange (warning) for ratings
  - Green (success) for favorites
  - Honest scales (no truncated axes)

### States Covered
- ✅ **Loading**: Spinner animation
- ✅ **Empty**: "No results found" with helpful message
- ✅ **Error**: Inline error display with details
- ✅ **Partial**: Shows available data even if incomplete

### Components
All using CSS primitives (no custom framework):
- KPI cards: white bg, border-left accent, shadow-sm
- Restaurant cards: grid layout, hover effects, semantic badges
- Search controls: flex layout, focus states
- No hardcoded hex colors - all CSS custom properties

## API Endpoints

- `GET /` - Main dashboard UI
- `GET /api/search?location=...&term=...` - Search restaurants
- `GET /api/details/<business_id>` - Restaurant details
- `GET /api/weather?lat=...&lon=...` - Weather data
- `GET /api/favorites` - User's saved restaurants
- `GET /healthz` - Health check

## Features

### Restaurant Notes
Users can save personal notes for any restaurant with:
- **Rich text notes** - Share experiences and impressions
- **Tags** - Organize notes with custom tags (e.g., "favorite", "date-night", "must-try")
- **Personal ratings** - Rate restaurants 0-5 independently of Yelp ratings
- **Visit dates** - Track when you visited
- **Full CRUD** - Create, read, update, and delete notes

Notes are displayed in a modal with a clean, organized UI:
- Notes button on each restaurant card with count badge
- Add new notes with inline form
- Edit and delete existing notes
- Filter notes by restaurant or view all

**Backend**: PostgreSQL table `restaurant_notes` via Lakebase  
**Frontend**: Modal UI with form validation and real-time updates  
**Documentation**: See [FRONTEND_NOTES_UI.txt](FRONTEND_NOTES_UI.txt) for integration guide

## Setup

1. Configure secrets in Databricks:
   ```bash
   databricks secrets create-scope --scope restaurant-app
   databricks secrets put --scope restaurant-app --key yelp-api-key
   databricks secrets put --scope restaurant-app --key lakebase-user
   databricks secrets put --scope restaurant-app --key lakebase-password
   ```

2. Update `app.yaml` with your Lakebase host

3. Deploy:
   ```bash
   databricks apps deploy app
   ```

## Reference

- Structure: `weather-intelligence-system/dashboard/`
- Design: `databricks-app-design` skill
- Patterns: KPI cards, semantic color, state handling

## Key Changes from Original

- **Flask instead of Streamlit**: Template-based rendering, matching reference
- **Flat structure**: No nested client/server folders
- **Minimal dependencies**: Only Flask, psycopg2, requests
- **Semantic color tokens**: CSS custom properties, no hardcoded hex
- **Proper states**: Loading, empty, error all handled
