/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string;
  readonly VITE_STRIPE_PUBLISHABLE_KEY?: string;
  readonly VITE_USE_DEMO_DATA?: string;
  readonly VITE_DEPLOYMENT_STAGE?: string;
  readonly VITE_DEMO_SANDBOX_ACKNOWLEDGED?: string;
}
