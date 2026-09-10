(() => {
  "use strict";
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [
    ...root.querySelectorAll(selector),
  ];
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const nf = new Intl.NumberFormat("en-NG");
  const money = (value) => "₦" + nf.format(Math.floor(value));
  const clamp = (n, min = 0, max = 1) => Math.max(min, Math.min(max, n));
  const smooth = (n) => {
    n = clamp(n);
    return n * n * (3 - 2 * n);
  };
  if (!reduced.matches) document.body.classList.add("motion-ready");

  // A single reveal per composition. Plain HTML stays visible if JS is unavailable.
  const revealNodes = $$("[data-reveal]");
  if (!reduced.matches && "IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.remove("awaiting");
          entry.target.classList.add("revealed");
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -35px 0px" },
    );
    revealNodes.forEach((el) => {
      el.classList.add("awaiting");
      observer.observe(el);
    });
  }

  const nav = $("#nav"),
    burger = $("#burger"),
    mobileNav = $("#mobileNav");
  function setMenu(open) {
    burger.setAttribute("aria-expanded", String(open));
    burger.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    mobileNav.hidden = !open;
  }
  burger.addEventListener("click", () =>
    setMenu(burger.getAttribute("aria-expanded") !== "true"),
  );
  mobileNav.addEventListener("click", (event) => {
    if (event.target.closest("a")) setMenu(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !mobileNav.hidden) {
      setMenu(false);
      burger.focus();
    }
  });
  addEventListener("resize", () => {
    if (innerWidth > 960) setMenu(false);
  });

  // Campaign filters retain stable card sizes instead of stretching a single match.
  $$(".filter").forEach((button) =>
    button.addEventListener("click", () => {
      $$(".filter").forEach((el) => {
        const selected = el === button;
        el.classList.toggle("is-active", selected);
        el.setAttribute("aria-pressed", String(selected));
      });
      $$(".campaign-card").forEach((card) => {
        card.hidden =
          button.dataset.filter !== "all" &&
          card.dataset.category !== button.dataset.filter;
      });
    }),
  );

  // Calculator follows the PRD: only complete thousands, minimum 1,000 views.
  const slider = $("#viewSlider"),
    rate = $("#rateSelect");
  function calculate() {
    const views = Number(slider.value),
      amount = Math.floor(views / 1000) * Number(rate.value);
    $("#calcViews").textContent = nf.format(views);
    $("#calcMoney").textContent = money(amount);
    slider.style.setProperty(
      "--fill",
      `${(views / Number(slider.max)) * 100}%`,
    );
    slider.setAttribute("aria-valuetext", `${nf.format(views)} verified views`);
  }
  slider.addEventListener("input", calculate);
  rate.addEventListener("change", calculate);
  calculate();

  // Native dialog provides keyboard focus containment and Escape handling.
  const dialog = $("#detailDialog"),
    dialogContent = $("#dialogContent");
  let returnFocus;
  function showDialog(html) {
    returnFocus = document.activeElement;
    dialogContent.innerHTML = html;
    dialog.showModal();
    document.documentElement.style.overflow = "hidden";
  }
  $(".dialog-close", dialog).addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const r = dialog.getBoundingClientRect();
    if (
      event.clientX < r.left ||
      event.clientX > r.right ||
      event.clientY < r.top ||
      event.clientY > r.bottom
    )
      dialog.close();
  });
  dialog.addEventListener("close", () => {
    document.documentElement.style.overflow = "";
    if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
  });
  const campaigns = {
    music: {
      brand: "Gbedu Records",
      title: "Put the next anthem on the map.",
      rate: 850,
      budget: 408000,
      platforms: "TikTok or YouTube Shorts",
      rules: [
        "Use the supplied campaign sound for at least 15 seconds.",
        "Make an original dance, transition, or music-led story.",
        "Include the campaign artist tag and #CreateWithClippit.",
        "Use only footage you own or have permission to use.",
      ],
    },
    lifestyle: {
      brand: "Everyday Lagos",
      title: "Your city. Through your lens.",
      rate: 500,
      budget: 340000,
      platforms: "TikTok or Instagram Reels",
      rules: [
        "Share an original moment from everyday life in Lagos.",
        "Keep the video between 15 and 60 seconds.",
        "Include the campaign tag and #CreateWithClippit.",
        "Ask permission before featuring an identifiable bystander.",
      ],
    },
    fashion: {
      brand: "Shuku Studios",
      title: "The fit deserves its own film.",
      rate: 620,
      budget: 880000,
      platforms: "Instagram Reels",
      rules: [
        "Show the campaign collection clearly in the video.",
        "Create an original styling, GRWM, or transition video.",
        "Tag the brand and include #CreateWithClippit.",
        "Do not make unsupported product or pricing claims.",
      ],
    },
  };
  $$("[data-campaign]").forEach((button) =>
    button.addEventListener("click", () => {
      const c = campaigns[button.dataset.campaign];
      showDialog(
        `<span class="mini-tag">Sample brief · ${c.brand}</span><h2 id="dialogTitle">${c.title}</h2><p>Make it for ${c.platforms}. Keep your own style.</p><div class="dialog__rate"><strong>${money(c.rate)}</strong><span>per 1,000 verified views</span></div><p>Example remaining budget: <b>${money(c.budget)}</b></p><h3>Your creative checklist</h3><ul>${c.rules.map((rule) => `<li>${rule}</li>`).join("")}</ul><h3>The money bit</h3><p>1,000 verified views to begin earning. Only complete thousands count. A five-day hold applies before approved earnings clear. Live campaigns will show the exact deadline, clip cap, and creator cap before you join.</p><div class="dialog__notice"><p>This is a campaign preview, not a live offer. You can explore the earnings calculation below; no account or submission is created.</p></div><button class="button" id="tryRate" style="margin-top:22px">Try this campaign rate <svg class="icon"><use href="#i-up"/></svg></button>`,
      );
      $("#tryRate").addEventListener("click", () => {
        rate.value = String(c.rate);
        calculate();
        dialog.close();
        $("#earnings").scrollIntoView({
          behavior: reduced.matches ? "instant" : "smooth",
        });
        slider.focus({ preventScroll: true });
      });
    }),
  );

  $$("[data-open]").forEach((button) =>
    button.addEventListener("click", () => {
      if (button.dataset.open === "credits") {
        showDialog(
          '<span class="mini-tag">The people behind the pictures</span><h2 id="dialogTitle">Good imagery. Proper credit.</h2><p>Photography sourced from Unsplash. The people pictured are models, not Clippit endorsers. Social layouts, campaign names, view counts, and earnings are illustrative.</p><div class="dialog__links"><a href="https://unsplash.com/photos/smiling-woman-wearing-turban-i2hoD-C2RUA" target="_blank" rel="noopener noreferrer">Lagos portrait — Prince Akachi ↗</a><a href="https://unsplash.com/photos/woman-wearing-white-blouse-and-black-cateye-sunglasses-4ar-CSxLcMg" target="_blank" rel="noopener noreferrer">Sunglasses portrait — Alex Robinson ↗</a><a href="https://unsplash.com/photos/stylish-woman-with-afro-hair-wearing-sunglasses-and-red-shirt-g95oS2hb7Rg" target="_blank" rel="noopener noreferrer">Afro & sunglasses — Divaris Shirichena ↗</a><a href="https://unsplash.com/photos/a-man-standing-on-a-sidewalk-wearing-headphones-fvHrDsKR0Gc" target="_blank" rel="noopener noreferrer">Street-style headphones portrait — Unsplash ↗</a></div>',
        );
        return;
      }
      showDialog(
        `<span class="mini-tag">Make the idea concrete</span><h2 id="dialogTitle">Your next big thing starts here.</h2><p>Build a sample brief and download it. This preview stays in your browser; it does not publish a campaign or collect payment.</p><form class="brand-form" id="brandForm"><label for="briefName">Campaign name</label><input id="briefName" name="title" maxlength="100" placeholder="Give your big idea a name" required><label for="briefBudget">Campaign budget (₦)</label><input id="briefBudget" name="budget" type="number" min="1000" max="1000000000" step="1" value="500000" required><label for="briefRate">Rate per 1,000 verified views (₦)</label><input id="briefRate" name="rate" type="number" min="1" max="1000000" step="1" value="500" required><output id="briefReach" aria-live="polite">This budget can fund 1,000,000 verified views.</output><label for="briefChecklist">What should creators say, show, or tag?</label><textarea id="briefChecklist" name="checklist" maxlength="3000" placeholder="One requirement per line. Keep it clear. Make room for creativity." required></textarea><button class="button" type="submit">Download my sample brief <svg class="icon"><use href="#i-arrow"/></svg></button><p id="briefStatus" role="status"></p></form>`,
      );
      const form = $("#brandForm");
      const updateReach = () => {
        const budget = Number($("#briefBudget").value),
          rateValue = Number($("#briefRate").value);
        $("#briefReach").textContent =
          budget > 0 &&
          rateValue > 0 &&
          form.elements.budget.validity.valid &&
          form.elements.rate.validity.valid
            ? `This budget can fund ${nf.format(Math.floor(budget / rateValue) * 1000)} verified views.`
            : "Enter a valid budget and rate to estimate funded views.";
      };
      form.addEventListener("input", updateReach);
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        const title = $("#briefName").value.trim(),
          checklist = $("#briefChecklist").value.trim();
        if (!title || !checklist) {
          $("#briefStatus").textContent =
            "Add a campaign name and at least one requirement.";
          return;
        }
        const text = `CLIPPIT — SAMPLE CAMPAIGN\n\n${title}\n\nBudget: ${money(Number($("#briefBudget").value))}\nRate: ${money(Number($("#briefRate").value))} per 1,000 verified views\n${$("#briefReach").textContent}\n\nCREATIVE CHECKLIST\n${checklist}\n\nBEFORE LAUNCH\nChoose supported platforms, a deadline, and clip and creator caps. Fund escrow before the campaign opens. Full thousands only; 1,000-view minimum; five-day holding period.\n\nThis is a local planning draft, not a published or funded campaign.\n`;
        const url = URL.createObjectURL(
          new Blob([text], { type: "text/plain;charset=utf-8" }),
        );
        const link = document.createElement("a");
        link.href = url;
        link.download = "clippit-campaign-brief.txt";
        document.body.append(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        $("#briefStatus").textContent =
          "Your brief is ready. Download started — keep creating.";
      });
    }),
  );

  // Confetti is finite and only consumes frames while particles are visible.
  const confetti = $("#confetti"),
    ctx = confetti.getContext("2d");
  let particles = [],
    confettiFrame = 0,
    confettiLast = 0;
  function confettiSize() {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    confetti.width = Math.round(innerWidth * dpr);
    confetti.height = Math.round(innerHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function confettiTick(time) {
    const delta = Math.min((time - (confettiLast || time)) / 16.67, 2.5);
    confettiLast = time;
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    particles = particles.filter((p) => p.life > 0 && p.y < innerHeight + 40);
    for (const p of particles) {
      p.x += p.vx * delta;
      p.y += p.vy * delta;
      p.vy += 0.12 * delta;
      p.vx *= 0.992;
      p.rotation += p.spin * delta;
      p.life -= delta;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rotation);
      ctx.globalAlpha = Math.min(1, p.life / 25);
      ctx.fillStyle = p.color;
      if (p.circle) {
        ctx.beginPath();
        ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2);
        ctx.fill();
      } else
        ctx.fillRect(
          -p.size / 2,
          -p.size / 4,
          p.size,
          (p.size / 2) * Math.cos(p.rotation),
        );
      ctx.restore();
    }
    if (particles.length && !document.hidden && !reduced.matches)
      confettiFrame = requestAnimationFrame(confettiTick);
    else {
      confettiFrame = 0;
      confettiLast = 0;
      ctx.clearRect(0, 0, innerWidth, innerHeight);
    }
  }
  function celebrate(amount = 100, rain = false) {
    if (reduced.matches || document.hidden || !ctx) return;
    if (!confettiFrame) confettiSize();
    const colors = ["#B8FF38", "#EFC884", "#7c9a50", "#ffffff"];
    for (let i = 0; i < amount; i++) {
      const left = i % 2 === 0;
      particles.push({
        x: rain ? Math.random() * innerWidth : left ? 0 : innerWidth,
        y: rain ? -20 - Math.random() * 130 : innerHeight * 0.68,
        vx: rain
          ? (Math.random() - 0.5) * 3
          : (left ? 1 : -1) * (3 + Math.random() * 9),
        vy: rain ? 1 + Math.random() * 2 : -5 - Math.random() * 9,
        size: 5 + Math.random() * 7,
        color: colors[i % colors.length],
        life: 180 + Math.random() * 70,
        rotation: Math.random() * 6,
        spin: (Math.random() - 0.5) * 0.2,
        circle: i % 5 === 0,
      });
    }
    particles = particles.slice(-260);
    if (!confettiFrame) confettiFrame = requestAnimationFrame(confettiTick);
  }
  $("#celebrate").addEventListener("click", () => celebrate(150));
  setTimeout(() => {
    if (scrollY < 200) celebrate(42, true);
  }, 1100);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      cancelAnimationFrame(confettiFrame);
      confettiFrame = 0;
      particles = [];
      ctx.clearRect(0, 0, innerWidth, innerHeight);
    }
  });

  // Retain the existing 84-frame throw, then match its final phone rectangle.
  const stage = $("[data-throw]"),
    canvas = $("#throwCanvas"),
    phone = $("#phone"),
    content = $("#phoneContent"),
    intro = $("#throwIntro");
  const throwContext = canvas.getContext("2d");
  let frames = [],
    loading = false,
    ready = false,
    failed = false,
    finaleCelebrated = false;
  let manifest = {
    frames: 84,
    w: 560,
    h: 820,
    final: { cx: 0.5, cy: 0.44, w: 0.1320267857, h: 0.186 },
  };
  let throwWidth = 0,
    throwHeight = 0,
    scheduled = false;
  const skip = document.createElement("button");
  skip.className = "throw-skip";
  skip.textContent = "Skip to the good part ↗";
  skip.addEventListener("click", () => {
    window.scrollTo({
      top: stage.offsetTop + stage.offsetHeight - innerHeight,
      behavior: "instant",
    });
    updateScene();
    $(".button", content).focus({ preventScroll: true });
  });
  intro.append(skip);
  function sizeThrow() {
    throwWidth = stage.clientWidth;
    throwHeight = innerHeight;
    const dpr = Math.min(devicePixelRatio || 1, 1.5);
    canvas.width = Math.round(throwWidth * dpr);
    canvas.height = Math.round(throwHeight * dpr);
    throwContext.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function fallbackThrow() {
    failed = true;
    stage.classList.remove("throw-enabled");
    phone.inert = false;
    phone.removeAttribute("style");
    content.removeAttribute("style");
  }
  async function loadFrames() {
    if (loading || failed || reduced.matches) return;
    loading = true;
    try {
      const response = await fetch("assets/throw/manifest.json");
      if (!response.ok) throw new Error("Missing animation manifest");
      manifest = await response.json();
      frames = await Promise.all(
        Array.from(
          { length: manifest.frames },
          (_, i) =>
            new Promise((resolve, reject) => {
              const image = new Image();
              image.onload = () => resolve(image);
              image.onerror = reject;
              image.src = `assets/throw/f${String(i).padStart(2, "0")}.webp`;
            }),
        ),
      );
      ready = true;
      sizeThrow();
      scheduleScene();
    } catch {
      fallbackThrow();
    }
  }
  function updateScene() {
    scheduled = false;
    nav.classList.toggle("is-stuck", scrollY > 10);
    if (reduced.matches || failed || !stage.classList.contains("throw-enabled"))
      return;
    const rect = stage.getBoundingClientRect();
    if (rect.top > innerHeight || rect.bottom < 0) return;
    if (!throwWidth) sizeThrow();
    const progress = clamp(
      -rect.top / Math.max(1, stage.offsetHeight - innerHeight),
    );
    const split = 0.53;
    // Desktop keeps the boy to the right of the copy; mobile uses the lower stage.
    const narrow = throwWidth < 700;
    const scale = Math.min(
      (throwWidth * (narrow ? 0.95 : 0.5)) / manifest.w,
      (throwHeight * (narrow ? 0.77 : 0.98)) / manifest.h,
    );
    const fw = manifest.w * scale,
      fh = manifest.h * scale;
    const fx = narrow ? (throwWidth - fw) / 2 : throwWidth * 0.69 - fw / 2;
    const fy = throwHeight - fh;
    intro.style.opacity = String(1 - smooth((progress - 0.13) / 0.22));
    intro.style.visibility = progress > 0.37 ? "hidden" : "visible";
    if (progress <= split) {
      phone.style.opacity = "0";
      phone.inert = true;
      canvas.style.opacity = "1";
      throwContext.clearRect(0, 0, throwWidth, throwHeight);
      if (ready) {
        const frame = Math.min(
          manifest.frames - 1,
          Math.floor((progress / split) * (manifest.frames - 1)),
        );
        throwContext.drawImage(frames[frame], fx, fy, fw, fh);
      }
      return;
    }
    const zoom = smooth((progress - split) / (1 - split));
    const startWidth = manifest.final.w * fw,
      startHeight = manifest.final.h * fh;
    const w = startWidth + (throwWidth - startWidth) * zoom;
    const h = startHeight + (throwHeight - startHeight) * zoom;
    const cx =
      fx +
      manifest.final.cx * fw +
      (throwWidth / 2 - fx - manifest.final.cx * fw) * zoom;
    const cy =
      fy +
      manifest.final.cy * fh +
      (throwHeight / 2 - fy - manifest.final.cy * fh) * zoom;
    Object.assign(phone.style, {
      width: `${w}px`,
      height: `${h}px`,
      left: `${cx - w / 2}px`,
      top: `${cy - h / 2}px`,
      borderRadius: `${w * 0.17 * (1 - smooth((zoom - 0.55) / 0.45))}px`,
      borderWidth: `${2 * (1 - zoom)}px`,
      opacity: "1",
    });
    Object.assign(content.style, {
      width: `${throwWidth}px`,
      height: `${throwHeight}px`,
      transform: `scale(${w / throwWidth})`,
      opacity: String(clamp((zoom - 0.12) / 0.3)),
    });
    canvas.style.opacity = zoom > 0.025 ? "0" : "1";
    phone.inert = zoom < 0.85;
    if (zoom > 0.98 && !finaleCelebrated) {
      finaleCelebrated = true;
      celebrate(110);
    }
  }
  function scheduleScene() {
    if (!scheduled) {
      scheduled = true;
      requestAnimationFrame(updateScene);
    }
  }
  if (!reduced.matches && throwContext) {
    stage.classList.add("throw-enabled");
    phone.inert = true;
    const preload = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          loadFrames();
          preload.disconnect();
        }
      },
      { rootMargin: "1800px" },
    );
    preload.observe(stage);
  }
  addEventListener("scroll", scheduleScene, { passive: true });
  addEventListener("resize", () => {
    sizeThrow();
    scheduleScene();
    if (confettiFrame) confettiSize();
  });
  reduced.addEventListener("change", () => {
    document.body.classList.toggle("motion-ready", !reduced.matches);
    if (reduced.matches) {
      revealNodes.forEach((el) => el.classList.remove("awaiting"));
      stage.classList.remove("throw-enabled");
      phone.inert = false;
      phone.removeAttribute("style");
      content.removeAttribute("style");
      cancelAnimationFrame(confettiFrame);
      confettiFrame = 0;
      particles = [];
      ctx.clearRect(0, 0, innerWidth, innerHeight);
    } else if (!failed) {
      stage.classList.add("throw-enabled");
      loadFrames();
      sizeThrow();
      scheduleScene();
    }
  });
  scheduleScene();
})();
