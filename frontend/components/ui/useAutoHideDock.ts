"use client";

import { useEffect, useState } from "react";

export function useAutoHideDock() {
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    let lastY = window.scrollY;
    let frame = 0;

    const update = () => {
      const nextY = window.scrollY;
      const distance = nextY - lastY;
      if (nextY < 48) setHidden(false);
      else if (distance > 7) setHidden(true);
      else if (distance < -7) setHidden(false);
      lastY = nextY;
      frame = 0;
    };

    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.cancelAnimationFrame(frame);
    };
  }, []);

  return hidden;
}
