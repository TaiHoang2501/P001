# BookingBot — Frontend

React 19 + TypeScript + Vite 6 + Tailwind CSS 4, TanStack Query, React Router.

## Run locally

Needs the backend running (see the root README). By default `/api` is proxied to
http://localhost:8000; set `API_PROXY` if the backend runs elsewhere.

```bash
cd frontend
npm install
npm run dev                                   # http://localhost:5173
API_PROXY=http://localhost:8001 npm run dev   # backend on another port (bash)
$env:API_PROXY="http://localhost:8001"; npm run dev   # PowerShell
```

Buyers and sellers can sign in with **Mã OTP**. With the backend's `OTP_PROVIDER=local` (default) no SMS is sent:
outside production the API returns the code and the login page shows it. With `OTP_PROVIDER=firebase` the API
answers `provider: "firebase"` plus the Firebase web config, and the page has Firebase Phone Auth send the SMS and
check the code (`src/auth/firebasePhone.ts`, loaded only then); no frontend env vars are needed.

Demo accounts (from `src/db/seed.py`, password `Password123!`):

| Role     | Login                                           |
|----------|-------------------------------------------------|
| Buyer    | `an.nguyen@gmail.com`, `binh.tran@gmail.com`    |
| Seller   | `tuan.pham@gmail.com`, `lan.hoang@gmail.com`    |
| Operator | `operator@vinhomes.vn`                          |

## API types

`src/api/schema.d.ts` is generated from the backend's OpenAPI spec. After changing backend
schemas or routes, regenerate it (backend must be running) and fix any type errors:

```bash
npm run gen:api
npm run typecheck
```

## Structure

```
src/
  api/          typed client (openapi-fetch), error handling, generated schema
  auth/         session context (JWT in localStorage) + role route guard
  components/   layout, property card, shared UI
  lib/format.ts Vietnamese labels for enums, VND/date formatting (Asia/Ho_Chi_Minh)
  pages/        buyer pages; owner/ (seller) and operator/ subfolders
```

Rules the UI follows (spec_final): a viewing is shown as *requested* until the seller
confirms it, and every request shows its Deal code; the seller never sees the buyer's name
or phone (privacy level 1); viewing times come from `POST /properties/{id}/viewing-times`
(buyer window ∩ seller availability); the AI chat page only calls `POST /api/v1/chat`
and renders cards, proposed times and bookings from the structured response.
