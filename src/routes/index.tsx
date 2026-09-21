import { createFileRoute, redirect } from "@tanstack/react-router";

// No head() here: the home route inherits title/description/og/twitter from
// __root.tsx, and ships no og:image so serve-time hosting can inject the
// project's social preview (explicit og:image or latest screenshot).
export const Route = createFileRoute("/")({
  beforeLoad: () => { throw redirect({ to: "/dashboard" }); },
  head: () => ({ meta: [
    { title: "DRISHTI — Narrative Intelligence" },
    { name: "description", content: "From scattered posts to one narrative timeline." },
    { property: "og:title", content: "DRISHTI — Narrative Intelligence" },
    { property: "og:description", content: "From scattered posts to one narrative timeline." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => null,
});
