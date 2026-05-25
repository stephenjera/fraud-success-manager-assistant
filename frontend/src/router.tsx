import React from "react";
import {
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
  Outlet,
  Link,
} from "@tanstack/react-router";
import QueryPage from "./pages/QueryPage";
import InvestigationPage from "./pages/InvestigationPage";

// 1. Create the root layout structure with FSM Portfolio Branding
const rootRoute = createRootRoute({
  component: () => (
    <div className="flex min-h-screen flex-col bg-slate-50/50 font-sans text-slate-800 antialiased">
      {/* Premium Merchant Risk telemetry Navigation Bar */}
      <nav className="sticky top-0 z-50 border-b border-slate-200 bg-white shadow-xs">
        <div className="mx-auto max-w-[1600px] px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            {/* Left side: Merchant Portfolio Brand Logo */}
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-600/20">
                <svg
                  className="h-5 w-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
              <div>
                <span className="block text-sm leading-none font-bold tracking-tight text-slate-900">
                  GuardRail
                </span>
                <span className="text-[10px] font-medium tracking-wider text-indigo-600 uppercase">
                  FSM Risk Intelligence
                </span>
              </div>
            </div>

            {/* Right side: Navigation Control Tabs */}
            <div className="flex items-center gap-2">
              <Link
                to="/"
                activeProps={{
                  className: "bg-indigo-50 text-indigo-600 border-indigo-200",
                }}
                inactiveProps={{
                  className:
                    "border-transparent text-slate-500 hover:text-slate-900 hover:bg-slate-50",
                }}
                className="flex cursor-pointer items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-bold tracking-wide transition-all"
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
                Query Studio
              </Link>

              <Link
                to="/investigation"
                activeProps={{
                  className: "bg-indigo-50 text-indigo-600 border-indigo-200",
                }}
                inactiveProps={{
                  className:
                    "border-transparent text-slate-500 hover:text-slate-900 hover:bg-slate-50",
                }}
                className="flex cursor-pointer items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-bold tracking-wide transition-all"
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
                  />
                </svg>
                FSM Investigation
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Page Workspace Content Mount Node */}
      <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  ),
});

// 2. Configure target paths routing configurations
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: QueryPage,
});

const investigationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/investigation",
  component: InvestigationPage,
});

// 3. Chain application route tree nodes
const routeTree = rootRoute.addChildren([indexRoute, investigationRoute]);

// 4. Instantiate central routing machine
const router = createRouter({
  routeTree,
});

// 5. Register router instance profile parameters for rigorous full type-safety
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

export default router;

// 6. Global wrapping provider initialization container
export function AppRouterProvider() {
  return <RouterProvider router={router} />;
}
