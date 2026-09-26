(() => {
  "use strict";
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [
    ...root.querySelectorAll(selector),
  ];
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  let motionAllowed = !reduced.matches;
  const nf = new Intl.NumberFormat("en-NG");
  const money = (value) => "₦" + nf.format(Math.floor(value));
  const clamp = (n, min = 0, max = 1) => Math.max(min, Math.min(max, n));
  const smooth = (n) => {
    n = clamp(n);
    return n * n * (3 - 2 * n);
  };
  if (!reduced.matches) document.body.classList.add("motion-ready");

  // Each composition has its own entrance; individual transforms preserve the
  // resting paper rotations in CSS. Finished animations release their styles.
  const revealNodes = $$("[data-reveal]");
  const entranceAnimations = new Set();
  const settle = "cubic-bezier(.22,1,.36,1)";
  function enter(target, keyframes, duration = 850, delay = 0) {
    if (!target || !motionAllowed || !target.animate) return;
    const animation = target.animate(keyframes, {
      duration,
      delay,
      easing: settle,
      fill: "both",
    });
    entranceAnimations.add(animation);
    const watchMotionPreference = () => {
      if (!entranceAnimations.has(animation)) return;
      if (reduced.matches) {
        animation.cancel();
        entranceAnimations.delete(animation);
        return;
      }
      requestAnimationFrame(watchMotionPreference);
    };
    requestAnimationFrame(watchMotionPreference);
    const release = () => {
      entranceAnimations.delete(animation);
      animation.cancel();
    };
    animation.finished.then(release, release);
  }
  function pop(target, delay, rotation = -12) {
    enter(
      target,
      [
        { opacity: 0, scale: ".45", rotate: `${rotation}deg` },
        { opacity: 1, scale: "1.09", rotate: "2deg", offset: 0.72 },
        { opacity: 1, scale: "1", rotate: "0deg" },
      ],
      720,
      delay,
    );
  }
  function land(target, delay = 0, angle = -6, distance = 70) {
    const travel = innerWidth < 700 ? distance * 0.65 : distance;
    enter(
      target,
      [
        {
          opacity: 0,
          translate: `0 ${travel}px`,
          rotate: `${angle}deg`,
          scale: ".93",
        },
        {
          opacity: 1,
          translate: "0 -7px",
          rotate: `${-angle * 0.16}deg`,
          scale: "1.012",
          offset: 0.72,
        },
        { opacity: 1, translate: "0 0", rotate: "0deg", scale: "1" },
      ],
      1100,
      delay,
    );
  }
  function rollNumber(target, delay) {
    enter(
      target,
      [
        { opacity: 0, translate: "0 18px", rotate: "-4deg", scale: ".92" },
        {
          opacity: 1,
          translate: "0 -3px",
          rotate: "1deg",
          scale: "1.025",
          offset: 0.7,
        },
        { opacity: 1, translate: "0 0", rotate: "0deg", scale: "1" },
      ],
      760,
      delay,
    );
  }
  function campaignEntrance(card, delay) {
    const index = $$(".campaign-card").indexOf(card);
    land(card, delay, [-7, 4, 8][index] || -5, 95);
    enter(
      $(".campaign-art > img", card),
      [
        { scale: "1.17", translate: "0 10px" },
        { scale: "1", translate: "0 0" },
      ],
      1350,
      delay + 100,
    );
    enter(
      $(".campaign-art__type", card),
      [
        { opacity: 0, translate: "0 28px", clipPath: "inset(0 0 100% 0)" },
        {
          opacity: 1,
          translate: "0 0",
          clipPath: "inset(-10% -70% -10% -10%)",
        },
      ],
      750,
      delay + 280,
    );
    pop($(".campaign-category", card), delay + 420, index % 2 ? 10 : -10);
    rollNumber($(".campaign-rate", card), delay + 430);
    enter(
      $(".pot-track > span", card),
      [{ scale: "0 1" }, { scale: "1 1" }],
      950,
      delay + 540,
    );
    pop($(".campaign-open > .icon", card), delay + 620, -45);
  }
  function stepEntrance(step, delay) {
    // Content stays calm while the miniature product objects do the storytelling.
    enter(step, [{ opacity: 0 }, { opacity: 1 }], 500, delay);
    const brief = $(".mini-brief", step),
      post = $(".mini-post", step);
    const proof = $(".proof-slip", step),
      receipt = $(".mini-receipt", step);
    if (brief) {
      enter(
        brief,
        [
          {
            opacity: 0,
            translate: "-75px 35px",
            rotate: "-20deg",
            scale: ".85",
          },
          {
            opacity: 1,
            translate: "4px -4px",
            rotate: "4deg",
            scale: "1.02",
            offset: 0.72,
          },
          { opacity: 1, translate: "0 0", rotate: "0deg", scale: "1" },
        ],
        1100,
        delay + 100,
      );
      pop($(".mini-brief__button", step), delay + 650, 0);
    }
    if (post) {
      enter(
        post,
        [
          { opacity: 0, rotate: "32deg", translate: "28px -90px" },
          { opacity: 1, rotate: "-8deg", translate: "-3px 4px", offset: 0.62 },
          { opacity: 1, rotate: "3deg", translate: "0 -2px", offset: 0.82 },
          { opacity: 1, rotate: "0deg", translate: "0 0" },
        ],
        1300,
        delay + 60,
      );
      pop($(".link-pill", step), delay + 610, -9);
    }
    if (proof) {
      land(proof, delay + 80, 5, 50);
      $$(".proof-slip > p", step).forEach((row, index) => {
        enter(
          row,
          [
            { opacity: 0, translate: "-14px 0" },
            { opacity: 1, translate: "0 0" },
          ],
          450,
          delay + 340 + index * 140,
        );
        pop($("i", row), delay + 460 + index * 140, -28);
      });
      rollNumber($(".proof-slip > div", step), delay + 780);
    }
    if (receipt) {
      enter(
        receipt,
        [
          {
            opacity: 0,
            translate: "0 -60px",
            scale: "1 .6",
            clipPath: "inset(0 0 95% 0)",
          },
          {
            opacity: 1,
            translate: "0 4px",
            scale: "1 1.03",
            clipPath: "inset(0 0 0 0)",
            offset: 0.82,
          },
          {
            opacity: 1,
            translate: "0 0",
            scale: "1 1",
            clipPath: "inset(0 0 0 0)",
          },
        ],
        1150,
        delay + 80,
      );
      pop($(".mini-receipt > .icon", step), delay + 580, 20);
      rollNumber($(".mini-receipt > strong", step), delay + 700);
    }
    enter(
      $(".step__visual > .hand-note", step),
      [
        { opacity: 0, clipPath: "inset(0 100% 0 0)" },
        { opacity: 1, clipPath: "inset(-25% -10% -25% -10%)" },
      ],
      650,
      delay + 750,
    );
  }
  function revealComposition(el, delay = 0) {
    el.classList.remove("awaiting");
    el.classList.add("revealed");
    if (reduced.matches) return;
    if (el.matches(".campaign-card")) return campaignEntrance(el, delay);
    if (el.matches(".step")) return stepEntrance(el, delay);
    if (el.matches(".calculator")) {
      land(el, delay, -7, 65);
      enter(
        $(".calculator__result", el),
        [
          { opacity: 0, scale: "1 .15", translate: "0 -15px" },
          { opacity: 1, scale: "1 1.04", translate: "0 2px", offset: 0.75 },
          { opacity: 1, scale: "1 1", translate: "0 0" },
        ],
        950,
        delay + 380,
      );
      rollNumber($("#calcMoney", el), delay + 700);
      pop($(".mini-tag", el), delay + 600);
    } else if (el.matches(".proof-board")) {
      land(el, delay, 8, 50);
      $$(".proof-board__row", el).forEach((row, index) => {
        enter(
          row,
          [
            { opacity: 0, translate: "-24px 8px", rotate: "-2deg" },
            { opacity: 1, translate: "0 0", rotate: "0deg" },
          ],
          650,
          delay + 300 + index * 180,
        );
      });
      $$(".proof-board__connector", el).forEach((arrow, index) =>
        pop(arrow, delay + 550 + index * 180, 0),
      );
      enter(
        $(".proof-board__tape", el),
        [{ scale: "0 1" }, { scale: "1 1" }],
        650,
        delay + 150,
      );
      pop($(".verified-stamp", el), delay + 1000, -28);
    } else if (el.matches(".brand-board")) {
      land(el, delay, -10, 70);
      $$(".brand-board__chart > div", el).forEach((bar, index) => {
        enter(
          bar,
          [
            { scale: "1 .03" },
            { scale: "1 1.08", offset: 0.8 },
            { scale: "1 1" },
          ],
          800,
          delay + 320 + index * 55,
        );
      });
      $$(".avatar-stack img", el).forEach((avatar, index) =>
        pop(avatar, delay + 800 + index * 100, -15),
      );
      enter(
        $(".brand-board__note", el),
        [
          { opacity: 0, translate: "-15px 0", rotate: "-8deg" },
          { opacity: 1, translate: "0 0", rotate: "0deg" },
        ],
        800,
        delay + 850,
      );
    } else {
      enter(
        el,
        [
          { opacity: 0, translate: "0 25px", rotate: "1.5deg" },
          { opacity: 1, translate: "0 0", rotate: "0deg" },
        ],
        850,
        delay,
      );
    }
  }
  let revealObserver;
  if (!reduced.matches && "IntersectionObserver" in window) {
    revealObserver = new IntersectionObserver(
      (entries) => {
        // Stagger only siblings entering together; a lone mobile card never waits
        // for the index it had in the desktop row.
        const visible = entries.filter((entry) => entry.isIntersecting);
        const groups = new Map();
        visible.forEach((entry) => {
          const parent = entry.target.parentElement;
          const order = groups.get(parent) || 0;
          groups.set(parent, order + 1);
          revealComposition(entry.target, Math.min(order * 130, 390));
          revealObserver.unobserve(entry.target);
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -35px 0px" },
    );
    revealNodes.forEach((el) => {
      el.classList.add("awaiting");
      revealObserver.observe(el);
    });
  }

  // Keyboard users can reach a card immediately, including during its entrance.
  document.addEventListener("focusin", (event) => {
    const card = event.target.closest("[data-reveal]");
    if (!card) return;
    card.classList.remove("awaiting");
    for (const animation of entranceAnimations) {
      if (card.contains(animation.effect?.target)) animation.cancel();
    }
  });

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
      let returning = 0;
      $$(".campaign-card").forEach((card) => {
        const wasHidden = card.hidden;
        card.hidden =
          button.dataset.filter !== "all" &&
          card.dataset.category !== button.dataset.filter;
        if (wasHidden && !card.hidden) {
          revealComposition(card, returning++ * 100);
        }
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
    finaleCelebrated = false,
    firstFramePromise = null;
  let manifest = {
    frames: 84,
    w: 560,
    h: 820,
    final: { cx: 0.5, cy: 0.44, w: 0.1320267857, h: 0.186 },
  };
  let throwWidth = 0,
    throwHeight = 0,
    scheduled = false;
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
  function loadFrame(index) {
    if (frames[index]) return Promise.resolve(frames[index]);
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.decoding = "async";
      image.fetchPriority = index === 0 ? "high" : "low";
      image.onload = () => {
        frames[index] = image;
        scheduleScene();
        resolve(image);
      };
      image.onerror = reject;
      image.src = `/assets/throw/f${String(index).padStart(2, "0")}.webp`;
    });
  }
  function loadFirstFrame() {
    if (!firstFramePromise) {
      firstFramePromise = loadFrame(0).then((image) => {
        ready = true;
        sizeThrow();
        scheduleScene();
        requestAnimationFrame(() => canvas.classList.add("has-frame"));
        return image;
      });
    }
    return firstFramePromise;
  }
  async function loadFrames() {
    if (loading || failed || reduced.matches) return;
    loading = true;
    try {
      await loadFirstFrame();
      const response = await fetch("/assets/throw/manifest.json");
      if (!response.ok) throw new Error("Missing animation manifest");
      manifest = await response.json();
      frames.length = manifest.frames;
      await Promise.all(Array.from({ length: manifest.frames - 1 }, (_, i) => loadFrame(i + 1)));
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
        let drawable = frames[frame];
        if (!drawable) {
          for (let distance = 1; distance < manifest.frames && !drawable; distance++) {
            drawable = frames[frame - distance] || frames[frame + distance];
          }
        }
        if (drawable) throwContext.drawImage(drawable, fx, fy, fw, fh);
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
  if (!reduced.matches && throwContext && innerWidth > 700) {
    stage.classList.add("throw-enabled");
    phone.inert = true;
    loadFirstFrame().catch(fallbackThrow);
    const preload = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          loadFrames();
          preload.disconnect();
        }
      },
      { rootMargin: "6000px 0px" },
    );
    preload.observe(stage);
    const warmThrow = () => loadFrames();
    if ("requestIdleCallback" in window) {
      requestIdleCallback(warmThrow, { timeout: 1400 });
    } else {
      setTimeout(warmThrow, 700);
    }
  }
  addEventListener("scroll", scheduleScene, { passive: true });
  addEventListener("resize", () => {
    sizeThrow();
    scheduleScene();
    if (confettiFrame) confettiSize();
  });
  reduced.addEventListener("change", () => {
    motionAllowed = !reduced.matches;
    document.body.classList.toggle("motion-ready", motionAllowed);
    if (reduced.matches) {
      revealObserver?.disconnect();
      entranceAnimations.forEach((animation) => animation.cancel());
      document.getAnimations().forEach((animation) => animation.cancel());
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
