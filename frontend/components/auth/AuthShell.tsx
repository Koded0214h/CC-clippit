"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { authRouteMeta } from "@/lib/auth";
import { Brand } from "@/components/ui/Brand";

export function AuthShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const meta = authRouteMeta[pathname] ?? authRouteMeta["/auth/sign-up"];
  const isSignIn = pathname === "/auth/sign-in";
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(true);

  useEffect(() => {
    const video = videoRef.current;
    const media = window.matchMedia(
      "(max-width: 860px), (prefers-reduced-motion: reduce)",
    );
    if (!video || !media.matches) return;
    video.pause();
    setPlaying(false);
  }, []);

  const toggleVideo = async () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      await video.play();
      setPlaying(true);
    } else {
      video.pause();
      setPlaying(false);
    }
  };

  return (
    <div className="auth-root">
      <a className="skip" href="#auth-content">
        Skip to the form
      </a>
      <header className="auth-nav">
        <Brand />
        <div className="auth-nav__aside">
          <span>{isSignIn ? "New around here?" : "Already making moves?"}</span>
          <Link href={isSignIn ? "/auth/sign-up" : "/auth/sign-in"}>
            {isSignIn ? "Sign up" : "Sign in"}
          </Link>
        </div>
      </header>
      <main className="auth-layout" id="auth-content">
        <section className="auth-workspace" aria-label="Clippit account access">
          <div className="auth-workspace__inner">
            <div className="route-meter" aria-hidden="true">
              <span className="route-meter__label">{meta.label}</span>
              <span className="route-meter__line">
                <i style={{ width: `${meta.progress}%` }} />
              </span>
              <span className="route-meter__count">{meta.count}</span>
            </div>
            {children}
          </div>
        </section>
        <aside
          className="auth-story"
          aria-label="A creator clip becoming verified earnings"
        >
          <video
            ref={videoRef}
            className="motion-stage__video"
            autoPlay
            muted
            loop
            playsInline
            poster="/assets/video/creator-reaction-poster.jpg"
          >
            <source
              src="/assets/video/creator-reaction.mp4"
              type="video/mp4"
              media="(min-width: 861px)"
            />
          </video>
          <div className="motion-stage__wash" aria-hidden="true" />
          <div className="comic-payment">
            <span className="comic-payment__check" aria-hidden="true">
              ✓
            </span>
            <p>
              You just received <strong>₦55,000</strong> for your Indomie
              content.
            </p>
          </div>
          <button
            className={`video-icon-control${playing ? "" : " is-paused"}`}
            type="button"
            onClick={toggleVideo}
            aria-label={playing ? "Pause creator video" : "Play creator video"}
          >
            <span />
          </button>
        </aside>
      </main>
    </div>
  );
}
