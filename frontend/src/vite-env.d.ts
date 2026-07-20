/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string;
  readonly VITE_PERSONA_TEMPLATE_ID?: string;
  readonly VITE_USE_DEMO_DATA?: string;
}
