# API Routes Configuration

## Backend API URL

All coffee detail API routes (`/api/coffees/[id]/*`) forward requests to the Python FastAPI backend.

The backend URL is configured via the `BACKEND_API_URL` environment variable:
- **Development**: `http://localhost:8000` (default, local Docker)
- **Production (Railway)**: `http://api.railway.internal:8000` (internal network)

If `BACKEND_API_URL` is not set, routes default to `http://localhost:8000`.

### Routes that require BACKEND_API_URL:
- `/api/coffees/[id]` - Coffee detail
- `/api/coffees/[id]/price-history` - Price history
- `/api/coffees/[id]/price-stats` - Price statistics
- `/api/coffees/[id]/taste-profile` - Taste profile
- `/api/coffees/[id]/similar` - Similar coffees

All routes follow the same pattern:
1. Receive request on Next.js API route
2. Construct backend URL with `BACKEND_API_URL` environment variable
3. Forward request to Python API
4. Return response as JSON
