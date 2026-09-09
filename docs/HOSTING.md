# Hosting guide: deploy the portfolio demo on Railway

## Recommended setup

Deploy this repository as **two Railway services in one project**:

```text
Public browser
      │
      ▼
Streamlit dashboard service ────────► FastAPI + MCP backend service
      public Railway domain              public Railway domain
      BACKEND_URL variable               DEMO_MODE=true
```

This is the easiest portfolio setup because both services deploy from the same GitHub repository and Railway manages the deployment variables. The backend is intentionally deployed with `DEMO_MODE=true`: visitors can exercise the catalog, quote, guardrails, and audit trail, but cannot call Groq or create Razorpay orders with your credentials.

The root [`railway.json`](../railway.json) configures the backend start command and `/health` deployment check. The dashboard uses the start command given below as a per-service override.

## Before you deploy

1. Create a new GitHub repository and push this project.
2. Confirm `.env` is not tracked. The repository should contain `.env.example`, never your real `.env`.
3. In the hosted public demo, **do not add** `GROQ_API_KEY`, `RAZORPAY_KEY_ID`, or `RAZORPAY_KEY_SECRET`. Demo mode does not need them.

```bash
git add README.md .gitignore .env.example .streamlit railway.json app docs requirements.txt test_*.py
git status
git commit -m "feat: prepare safe Railway portfolio deployment"
git push -u origin main
```

## Step 1: deploy the backend

1. Sign in to Railway and create a **New Project**.
2. Choose **Deploy from GitHub repo**, authorize GitHub if prompted, and select this repository.
3. Name the service `backend`.
4. Railway reads `railway.json`; confirm the start command is:

   ```text
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

5. Open the service **Variables** tab and add:

   ```text
   DEMO_MODE=true
   ENVIRONMENT=portfolio
   CORS_ORIGINS=*
   MAX_DISCOUNT_PERCENTAGE=20.0
   MAX_TRANSACTION_LIMIT_INR=10000.0
   ```

6. Under **Settings → Networking**, select **Generate Domain**. Save the resulting URL, for example `https://your-backend.up.railway.app`.
7. Under **Settings → Deploy**, confirm the health-check path is `/health`.
8. Open `https://your-backend.up.railway.app/health`. You should see `"status": "healthy"` and `"demo_mode": true`.

Railway injects the `PORT` variable used by the start command, and it uses the same port when running a configured health check. A deployment only becomes active after that route returns a successful response. See Railway’s [FastAPI deployment guide](https://docs.railway.com/guides/fastapi) and [health-check documentation](https://docs.railway.com/deployments/healthchecks).

## Step 2: deploy the dashboard

1. In the **same Railway project**, choose **New Service → GitHub Repo** and select the same repository again.
2. Name this service `dashboard`.
3. In the dashboard service settings, override its start command with:

   ```text
   streamlit run app/dashboard.py --server.address 0.0.0.0 --server.port $PORT
   ```

4. In the dashboard service **Variables** tab, add:

   ```text
   BACKEND_URL=https://your-backend.up.railway.app
   ```

   Use the backend domain from Step 1, with no trailing slash.

5. Under **Settings → Networking**, generate a public domain for the dashboard.
6. Open that URL, submit the default keyboard request, and confirm that the result says it is a simulated demo transaction.

## Step 3: tighten CORS after the dashboard domain exists

Replace the backend’s temporary wildcard with the exact dashboard domain:

```text
CORS_ORIGINS=https://your-dashboard.up.railway.app
```

Redeploy the backend. Use comma-separated values if you host a second trusted dashboard domain. Do not include a trailing slash.

## What to link in your portfolio

- **Live demo:** the dashboard Railway domain.
- **API documentation:** `https://your-backend.up.railway.app/docs`.
- **MCP endpoint:** `https://your-backend.up.railway.app/mcp`.
- **Source and architecture:** GitHub repository, root README, and `docs/ARCHITECTURE.md`.

Add a short label beside the live demo: “Public simulation — catalog, guardrails, and audit trail are live; no real payments are accepted.”

## Optional: run the real Test Mode integration privately

For a private, controlled testing environment only, create a separate backend service or environment with:

```text
DEMO_MODE=false
GROQ_API_KEY=<your secret>
RAZORPAY_KEY_ID=<your Razorpay Test Mode key>
RAZORPAY_KEY_SECRET=<your Razorpay Test Mode secret>
LLM_MODEL=openai/gpt-oss-120b
LLM_BASE_URL=https://api.groq.com/openai/v1
```

Keep that service unlinked from a public dashboard until you add authentication, rate limits, signed buyer mandates, and payment/webhook controls. Railway variables are supplied at build and runtime; set sensitive values in the Railway Variables UI, not in Git. [Railway variables documentation](https://docs.railway.com/variables)

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Backend deploy fails to start | Verify the start command uses `app.main:app`, `0.0.0.0`, and `$PORT`. |
| Health check fails | Set the backend health-check path to `/health`; test the generated backend URL directly. |
| Dashboard cannot reach the API | Verify `BACKEND_URL` is the full backend HTTPS URL and the backend is public. |
| Browser reports a CORS error | Set backend `CORS_ORIGINS` to the exact dashboard origin, no trailing slash, then redeploy. |
| Dashboard creates a real order | Stop sharing its URL and confirm backend `DEMO_MODE=true`; public demo mode should not contain provider secrets. |

## Alternative: Streamlit Community Cloud

You can host only the dashboard on Streamlit Community Cloud and keep the backend on Railway. Deploy `app/dashboard.py` from GitHub, then set `BACKEND_URL` in the app’s secret/settings area to the Railway backend domain. Streamlit Community Cloud deploys from a repository and supports deployment-time secrets/settings. [Streamlit deployment docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

For this project, two Railway services are simpler because both pieces use the same deployment workflow and project variables.
