/* ===================================================================
   HobbyFi — landing page interactions (front-end only, no backend)
   =================================================================== */
(function () {
  "use strict";

  /* ---------------- nav: scrolled state + mobile toggle ---------------- */
  const nav = document.getElementById("nav");
  const navToggle = document.getElementById("navToggle");
  const navLinks = document.getElementById("navLinks");

  const onScroll = () => nav.classList.toggle("is-scrolled", window.scrollY > 8);
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  navToggle.addEventListener("click", () => {
    const open = navLinks.classList.toggle("is-open");
    navToggle.setAttribute("aria-expanded", String(open));
  });
  navLinks.querySelectorAll("a").forEach((a) =>
    a.addEventListener("click", () => {
      navLinks.classList.remove("is-open");
      navToggle.setAttribute("aria-expanded", "false");
    })
  );

  /* ---------------- hero floating chat ---------------- */
  const heroScript = [
    { who: "user", text: "What was my revenue today?" },
    { who: "bot", text: "Today: <b>$1,284</b> across 3 titles — up 12% vs yesterday." },
    { who: "user", text: "Extend Maya's trial by 14 days" },
    { who: "bot", text: "I'll propose that. Approve it in your portal to apply ✦" },
  ];
  const heroBody = document.getElementById("heroChatBody");
  let heroIdx = 0;

  function heroStep() {
    if (!heroBody || heroIdx >= heroScript.length) return;
    const item = heroScript[heroIdx++];

    if (item.who === "user") {
      const el = document.createElement("div");
      el.className = "msg msg--user";
      el.textContent = item.text;
      heroBody.appendChild(el);
      setTimeout(heroStep, 900);
    } else {
      const typing = document.createElement("div");
      typing.className = "msg msg--bot";
      typing.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
      heroBody.appendChild(typing);
      setTimeout(() => {
        typing.innerHTML = item.text;
        setTimeout(heroStep, 1500);
      }, 800);
    }
  }
  setTimeout(heroStep, 700);

  /* ---------------- demo: interactive copilot ---------------- */
  const log = document.getElementById("demoLog");
  const form = document.getElementById("demoForm");
  const input = document.getElementById("demoInput");
  const suggest = document.getElementById("demoSuggest");
  const proposalsEl = document.getElementById("demoProposals");
  const proposalsEmpty = document.getElementById("proposalsEmpty");
  const pendingCount = document.getElementById("pendingCount");
  const auditEl = document.getElementById("demoAudit");
  const resetBtn = document.getElementById("demoReset");

  let pending = 0;
  let proposalSeq = 0;

  const now = () => {
    const d = new Date();
    return d.toTimeString().slice(0, 8);
  };

  function addAudit(text, kind) {
    const li = document.createElement("li");
    if (kind) li.className = kind;
    li.innerHTML = '<span class="t">' + now() + "</span>" + text;
    // drop the "awaiting" placeholder if present
    const placeholder = auditEl.querySelector("li.empty");
    if (placeholder) placeholder.remove();
    auditEl.insertBefore(li, auditEl.firstChild);
  }

  function addBubble(text, who, typing) {
    const el = document.createElement("div");
    el.className = "bubble bubble--" + who + (typing ? " is-typing" : "");
    if (typing) {
      el.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
    } else {
      el.innerHTML = text;
    }
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  function refreshPending() {
    pendingCount.textContent = String(pending);
    pendingCount.setAttribute("data-zero", pending === 0 ? "true" : "false");
    if (proposalsEmpty) proposalsEmpty.style.display = pending === 0 ? "" : "none";
  }

  // canned responses — a tiny front-end "brain"
  function respond(query) {
    const q = query.toLowerCase();

    if (/revenue|sales|today|mrr|money|earn/.test(q)) {
      return {
        say:
          'Today: <b>$1,284</b> across 3 titles (Badminton Kings, Loomwood Tales, Tiny Planet). Up <b>12%</b> vs yesterday.' +
          '<table class="answer-table"><tr><th>Title</th><th>Revenue</th><th>Δ</th></tr>' +
          "<tr><td>Badminton Kings</td><td>$642</td><td>+18%</td></tr>" +
          "<tr><td>Loomwood Tales</td><td>$401</td><td>+4%</td></tr>" +
          "<tr><td>Tiny Planet</td><td>$241</td><td>+9%</td></tr></table>",
        audit: "Read · revenue summary for vendor:pixelforge",
        kind: "read",
      };
    }

    if (/trial|trialing|free users/.test(q) && /badminton/.test(q)) {
      return {
        say:
          '2 trial users on <b>Badminton Kings</b>:' +
          '<table class="answer-table"><tr><th>User</th><th>Since</th><th>Trial ends</th></tr>' +
          "<tr><td>Maya R.</td><td>Jul 06</td><td>Jul 20</td></tr>" +
          "<tr><td>Devon K.</td><td>Jul 09</td><td>Jul 23</td></tr></table>",
        audit: "Read · trial users for game:badminton_kings",
        kind: "read",
      };
    }

    if (/extend|increase|add|plus|\+/.test(q) && /trial/.test(q)) {
      // parse a name-ish token and days
      const daysMatch = q.match(/(\d+)\s*(?:day|d\b)/);
      const days = daysMatch ? daysMatch[1] : "14";
      const name = /maya/.test(q) ? "Maya R." : /devon/.test(q) ? "Devon K." : "selected user";
      return makeProposal(name, days);
    }

    if (/update|change|set|edit/.test(q)) {
      return makeProposal("selected record", "1");
    }

    // generic read-ish fallback
    return {
      say:
        "I can answer questions about <code>revenue</code>, <code>users</code>, and <code>trials</code> — and propose <code>writes</code> for your approval. Try a sample below ⤵",
      audit: "Read · help response",
      kind: "read",
    };
  }

  function makeProposal(name, days) {
    proposalSeq += 1;
    const id = "wp_" + Math.random().toString(36).slice(2, 6);
    const pid = "PR-" + String(1000 + proposalSeq);

    const el = document.createElement("div");
    el.className = "proposal";
    el.dataset.id = pid;
    el.innerHTML =
      '<div class="proposal__top"><span class="proposal__tag">PROPOSAL</span><span class="proposal__id">' +
      pid +
      "</span></div>" +
      '<div class="proposal__title">Extend free trial for ' +
      name +
      " by " +
      days +
      " days</div>" +
      '<div class="proposal__rows">' +
      '<div class="row"><b>action</b><span>extend_trial</span></div>' +
      '<div class="row"><b>user</b><span>' +
      name +
      "</span></div>" +
      '<div class="row"><b>trial_ends</b><span class="old">Jul 20</span> → <span class="new">Aug 03</span></div>' +
      '<div class="row"><b>vendor_id</b><span style="color:var(--cyan)">pixelforge</span></div>' +
      '<div class="row"><b>idempotency</b><span>' +
      id +
      "</span></div>" +
      "</div>" +
      '<div class="proposal__actions">' +
      '<button class="btn btn--approve" data-act="approve">Approve</button>' +
      '<button class="btn btn--reject" data-act="reject">Reject</button></div>';

    proposalsEl.appendChild(el);
    pending += 1;
    refreshPending();

    el.querySelector('[data-act="approve"]').addEventListener("click", () => resolveProposal(el, pid, "approve"));
    el.querySelector('[data-act="reject"]').addEventListener("click", () => resolveProposal(el, pid, "reject"));

    return {
      say:
        "I won't change anything yet. I've created <b>" +
        pid +
        "</b> — a pending proposal to extend " +
        name +
        "'s trial by " +
        days +
        " days. Approve it from the side panel to execute.",
      audit: "Write proposed · " + pid + " (awaiting human decision)",
      kind: null,
    };
  }

  function resolveProposal(el, pid, decision) {
    if (el.classList.contains("is-resolved")) return;
    el.classList.add("is-resolved");
    const res = document.createElement("div");
    res.className = "proposal__resolved " + (decision === "approve" ? "ok" : "no");
    res.textContent = decision === "approve" ? "✓ Approved &amp; executed" : "✕ Rejected — no change";
    res.innerHTML = decision === "approve" ? "✓ Approved &amp; executed" : "✕ Rejected — no change";
    el.appendChild(res);

    pending = Math.max(0, pending - 1);
    refreshPending();

    if (decision === "approve") {
      addBubble("✓ " + pid + " approved — trial extended. Idempotency key honored, no double-apply.", "bot");
      addAudit(pid + " · APPROVED &amp; executed", "ok");
    } else {
      addBubble("✕ " + pid + " rejected. Nothing changed in your data.", "bot");
      addAudit(pid + " · REJECTED", "no");
    }
  }

  function handleQuery(raw) {
    const text = (raw || "").trim();
    if (!text) return;

    addBubble(text, "user");
    input.value = "";

    const typing = addBubble("", "bot", true);
    setTimeout(() => {
      const r = respond(text);
      typing.className = "bubble bubble--bot";
      typing.innerHTML = r.say;
      log.scrollTop = log.scrollHeight;
      if (r.audit) addAudit(r.audit, r.kind);
    }, 650);
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    handleQuery(input.value);
  });
  suggest.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-q]");
    if (btn) handleQuery(btn.dataset.q);
  });

  resetBtn.addEventListener("click", () => {
    log.innerHTML = "";
    proposalsEl.innerHTML = "";
    proposalsEl.appendChild(proposalsEmpty);
    proposalsEmpty.style.display = "";
    auditEl.innerHTML = '<li class="empty">Awaiting activity…</li>';
    pending = 0;
    proposalSeq = 0;
    refreshPending();
    addBubble("Hi! I'm HobbyFi. Ask me about revenue, users, or trials — or tell me to change something and I'll propose it.", "bot");
  });

  // seed the demo with a friendly opener
  addBubble("Hi! I'm HobbyFi. Ask me about revenue, users, or trials — or tell me to change something and I'll propose it.", "bot");

  /* ---------------- scroll reveal ---------------- */
  const revealEls = document.querySelectorAll(".card, .step, .metric, .demo, .safety, .section__head");
  revealEls.forEach((el) => el.classList.add("reveal"));

  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    revealEls.forEach((el) => io.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("is-in"));
  }

  /* ---------------- metric counters ---------------- */
  const counters = document.querySelectorAll(".metric__num");
  function animateCount(el) {
    const to = parseFloat(el.dataset.to);
    const decimals = parseInt(el.dataset.decimals || "0", 10);
    const suffix = el.dataset.suffix || "";
    const zero = el.dataset.zero === "1";
    if (zero) {
      el.textContent = "0";
      return;
    }
    const dur = 1400;
    const start = performance.now();
    function tick(t) {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      const val = (to * eased).toFixed(decimals);
      el.textContent = val + suffix;
      if (p < 1) requestAnimationFrame(tick);
      else el.textContent = to.toFixed(decimals) + suffix;
    }
    requestAnimationFrame(tick);
  }

  if ("IntersectionObserver" in window) {
    const cio = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            animateCount(entry.target);
            cio.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.5 }
    );
    counters.forEach((c) => cio.observe(c));
  } else {
    counters.forEach(animateCount);
  }
})();
