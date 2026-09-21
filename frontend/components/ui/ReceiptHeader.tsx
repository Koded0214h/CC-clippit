"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import styles from "./ReceiptHeader.module.css";

export function ReceiptHeader({ title, reference }: { title: string; reference: string }) {
  return <><ReceiptWatermark /><header className={styles.header}>
    <div className={styles.brand}>
      <Image src="/assets/clippit-mark.png" width={38} height={38} alt="Clippit" />
      <span><strong>Clippit</strong><small>{title}</small></span>
    </div>
    <div className={styles.reference}><small>Document reference</small><strong>{reference}</strong></div>
  </header></>;
}

export function ReceiptWatermark() {
  const [target, setTarget] = useState<HTMLElement | null>(null);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setTarget(document.body);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);
  if (!target) return null;
  return createPortal(<div className={styles.watermark} aria-hidden="true" data-receipt-watermark>
    {Array.from({ length: 12 }, (_, index) => <Image key={index} src="/assets/clippit-mark.png" width={116} height={116} alt="" draggable={false} priority unoptimized />)}
  </div>, target);
}
