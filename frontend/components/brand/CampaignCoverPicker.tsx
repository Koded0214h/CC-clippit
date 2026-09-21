"use client";

import Image from "next/image";
import { useRef, useState, type ChangeEvent } from "react";
import { ProductIcon } from "@/components/ui/ProductIcon";

async function prepareCampaignCover(file: File) {
  if (!file.type.startsWith("image/")) throw new Error("Choose a JPG, PNG or WebP image.");
  if (file.size > 12 * 1024 * 1024) throw new Error("Choose an image smaller than 12 MB.");
  const source = URL.createObjectURL(file);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new window.Image();
      element.onload = () => resolve(element);
      element.onerror = () => reject(new Error("That image could not be opened."));
      element.src = source;
    });
    const ratio = 16 / 9;
    const sourceRatio = image.naturalWidth / image.naturalHeight;
    const sourceWidth = sourceRatio > ratio ? image.naturalHeight * ratio : image.naturalWidth;
    const sourceHeight = sourceRatio > ratio ? image.naturalHeight : image.naturalWidth / ratio;
    const width = Math.min(1440, Math.max(960, Math.round(sourceWidth)));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = Math.round(width / ratio);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("That image could not be prepared.");
    context.drawImage(image, (image.naturalWidth - sourceWidth) / 2, (image.naturalHeight - sourceHeight) / 2, sourceWidth, sourceHeight, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.86);
  } finally {
    URL.revokeObjectURL(source);
  }
}

export function CampaignCoverPicker({ value, title, onChange }: { value: string; title: string; onChange: (value: string) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const pick = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setWorking(true);
    setError("");
    try { onChange(await prepareCampaignCover(file)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "That image could not be used."); }
    finally { setWorking(false); }
  };
  return <section className={`campaign-cover-picker${value ? " has-cover" : ""}`}>
    <button type="button" className="campaign-cover-frame" onClick={() => input.current?.click()} disabled={working}>
      {value ? <Image src={value} alt={`${title || "Campaign"} cover preview`} fill unoptimized sizes="(max-width: 700px) 100vw, 640px" /> : <span><ProductIcon name="camera" /><strong>Add campaign cover</strong><small>Use the image creators should recognise first.</small></span>}
      <i><ProductIcon name="upload" />{working ? "Preparing…" : value ? "Replace cover" : "Choose image"}</i>
    </button>
    <div><p><strong>{value ? "Cover ready" : "Campaign image"}</strong><small>Optional. JPG, PNG or WebP up to 12 MB. Cropped to 16:9.</small></p>{value && <button type="button" onClick={() => { onChange(""); setError(""); }}>Remove</button>}</div>
    {error && <p className="campaign-cover-error" role="alert">{error}</p>}
    <input ref={input} className="campaign-cover-input" type="file" accept="image/jpeg,image/png,image/webp" onChange={pick} tabIndex={-1} />
  </section>;
}
