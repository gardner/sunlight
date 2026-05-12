import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface PageProps {
  params: Promise<{ slug: string }>;
}

// @ts-ignore
const mdFiles = import.meta.glob("../../content/*.md", { query: "?raw", import: "default" });

export default async function MarkdownPage(props: PageProps) {
  const { slug } = await props.params;

  const loadContent = mdFiles[`../../content/${slug}.md`];

  if (!loadContent) {
    return (
      <main className="flex-grow max-w-max-width mx-auto px-margin-mobile md:px-margin-desktop py-24 w-full">
        <h1 className="font-display text-display text-primary mb-4">404 - Page Not Found</h1>
        <p className="font-body-lg text-on-surface-variant">The requested page could not be found.</p>
        <a href="/" className="inline-flex mt-8 text-primary font-bold hover:underline">← Return Home</a>
      </main>
    );
  }

  const content = await loadContent() as string;

  return (
    <main className="flex-grow max-w-3xl mx-auto px-margin-mobile py-24 w-full prose prose-slate prose-headings:font-display prose-a:text-primary prose-a:font-semibold">
      <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
    </main>
  );
}
