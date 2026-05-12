"use client";

import DOMPurify from "dompurify";
import { useEffect, useState } from "react";

export function SafeHtml({ html }: { html: string }) {
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  if (!isMounted) {
    return <div className="animate-pulse h-10 bg-surface-container-high rounded" />;
  }

  return <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }} />;
}
