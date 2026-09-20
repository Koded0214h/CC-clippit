"use client";

import Image from "next/image";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { ProductIcon } from "@/components/ui/ProductIcon";

export type ProfileRole = "creator" | "brand";
export type StoredProfile = { name: string; bio: string; photo: string };

const PROFILE_EVENT = "clippit:profile-updated";

function storageKey(role: ProfileRole) {
  return `clippit:${role}-profile`;
}

export function readStoredProfile(role: ProfileRole, fallback: StoredProfile): StoredProfile {
  if (typeof window === "undefined") return fallback;
  try {
    const direct = window.localStorage.getItem(storageKey(role));
    if (direct) return { ...fallback, ...JSON.parse(direct) };
    const onboarding = window.localStorage.getItem(`clippit:${role}-onboarding`);
    if (!onboarding) return fallback;
    const data = JSON.parse(onboarding) as Record<string, string>;
    return {
      name: role === "brand" ? data.organisation || data.name || fallback.name : data.name || fallback.name,
      bio: data.description || fallback.bio,
      photo: data.photo || fallback.photo,
    };
  } catch {
    return fallback;
  }
}

export function saveStoredProfile(role: ProfileRole, profile: StoredProfile) {
  window.localStorage.setItem(storageKey(role), JSON.stringify(profile));
  window.dispatchEvent(new CustomEvent(PROFILE_EVENT, { detail: { role, profile } }));
}

export function useStoredProfile(role: ProfileRole, fallback: StoredProfile) {
  const [profile, setProfile] = useState(fallback);

  useEffect(() => {
    const sync = () => setProfile(readStoredProfile(role, fallback));
    const syncCustom = (event: Event) => {
      const detail = (event as CustomEvent<{ role: ProfileRole; profile: StoredProfile }>).detail;
      if (detail?.role === role) setProfile(detail.profile);
    };
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener(PROFILE_EVENT, syncCustom);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(PROFILE_EVENT, syncCustom);
    };
  }, [fallback, role]);

  return profile;
}

async function compressPhoto(file: File) {
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
    const edge = 720;
    const scale = Math.min(1, edge / Math.max(image.naturalWidth, image.naturalHeight));
    const width = Math.max(1, Math.round(image.naturalWidth * scale));
    const height = Math.max(1, Math.round(image.naturalHeight * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("That image could not be prepared.");
    context.fillStyle = "#f7f8f2";
    context.fillRect(0, 0, width, height);
    context.drawImage(image, 0, 0, width, height);
    return canvas.toDataURL("image/jpeg", 0.84);
  } finally {
    URL.revokeObjectURL(source);
  }
}

export function ProfilePhotoPicker({
  value,
  name,
  onChange,
  tone = "lime",
  compact = false,
}: {
  value: string;
  name: string;
  onChange: (value: string) => void;
  tone?: "lime" | "gold";
  compact?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const initials = name.trim().split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase() || "YOU";

  const pick = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setWorking(true);
    setError("");
    try {
      onChange(await compressPhoto(file));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "That image could not be used.");
    } finally {
      setWorking(false);
    }
  };

  return <div className={`profile-photo-picker profile-photo-picker--${tone}${compact ? " is-compact" : ""}`}>
    <div className="profile-photo-frame">
      {value ? <Image src={value} alt={`${name || "Profile"} preview`} fill unoptimized sizes={compact ? "120px" : "220px"} /> : <strong>{initials}</strong>}
      <span><ProductIcon name="camera" /></span>
    </div>
    <div className="profile-photo-copy">
      <strong>{value ? "Photo ready" : "Add a profile photo"}</strong>
      <small>JPG, PNG or WebP. You can change it later.</small>
      <div>
        <button type="button" onClick={() => input.current?.click()} disabled={working}><ProductIcon name="upload" />{working ? "Preparing…" : value ? "Replace photo" : "Choose photo"}</button>
        {value && <button type="button" className="profile-photo-remove" onClick={() => { onChange(""); setError(""); }}>Remove</button>}
      </div>
      {error && <p role="alert">{error}</p>}
    </div>
    <input ref={input} className="profile-photo-input" type="file" accept="image/jpeg,image/png,image/webp" onChange={pick} tabIndex={-1} />
  </div>;
}

export function ProfileAvatar({ profile, fallback, className }: { profile: StoredProfile; fallback: string; className: string }) {
  return <span className={className}>{profile.photo ? <Image src={profile.photo} alt="" fill unoptimized sizes="64px" /> : fallback}</span>;
}
