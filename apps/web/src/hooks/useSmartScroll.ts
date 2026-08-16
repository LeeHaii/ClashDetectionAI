import { useEffect, useRef } from "react";

export function useSmartScroll(dependency: unknown) {
  const ref = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);

  useEffect(() => {
    const node = ref.current;
    if (node && nearBottom.current) node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [dependency]);

  const onScroll = () => {
    const node = ref.current;
    if (!node) return;
    nearBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < 120;
  };
  return { ref, onScroll };
}

