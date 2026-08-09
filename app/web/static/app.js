// Vanilla, minimal - CLAUDE.md Stack table. Rule 9: log dwell_seconds.
(function () {
  var article = document.querySelector(".article-full[data-url-hash]");
  if (!article) return;

  var hash = article.dataset.urlHash;
  var openedAt = Date.now();

  function reportDwell() {
    var dwellSeconds = Math.round((Date.now() - openedAt) / 1000);
    var payload = JSON.stringify({ dwell_seconds: dwellSeconds });
    if (navigator.sendBeacon) {
      navigator.sendBeacon(
        "/article/" + hash + "/close",
        new Blob([payload], { type: "application/json" })
      );
    } else {
      fetch("/article/" + hash + "/close", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: true,
      });
    }
  }

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") reportDwell();
  });
})();

// Density toggle - EDITION-AND-UI.md §6.5. Client-side only, no reload:
// a data-density attribute on <body> drives app.css's rules.
(function () {
  var KEY = "aakasavani:density";
  var VALID = ["compact", "comfortable", "visual"];

  var stored = localStorage.getItem(KEY);
  var density = VALID.indexOf(stored) !== -1 ? stored : "comfortable";
  document.body.setAttribute("data-density", density);

  var buttons = document.querySelectorAll("[data-density-option]");
  for (var i = 0; i < buttons.length; i++) {
    (function (btn) {
      if (btn.dataset.densityOption === density) btn.classList.add("active");
      btn.addEventListener("click", function () {
        density = btn.dataset.densityOption;
        localStorage.setItem(KEY, density);
        document.body.setAttribute("data-density", density);
        for (var j = 0; j < buttons.length; j++) {
          buttons[j].classList.toggle("active", buttons[j] === btn);
        }
      });
    })(buttons[i]);
  }
})();

// Section/topic chip selection persistence - EDITION-AND-UI.md §2.3.
// Chips are plain links (server-rendered filtering); this only restores
// the last choice when the reader lands on a bare "/" with no filter in
// the URL at all - an explicit link always wins over a stored value.
(function () {
  var SECTION_KEY = "aakasavani:section";
  var TOPIC_KEY = "aakasavani:topic";

  var chips = document.querySelectorAll(
    ".chips a[data-section], .chips a[data-topic]"
  );
  for (var i = 0; i < chips.length; i++) {
    chips[i].addEventListener("click", function () {
      if (this.dataset.section !== undefined) {
        localStorage.setItem(SECTION_KEY, this.dataset.section);
      }
      if (this.dataset.topic !== undefined) {
        localStorage.setItem(TOPIC_KEY, this.dataset.topic);
      }
    });
  }

  if (window.location.pathname === "/" && window.location.search === "") {
    var section = localStorage.getItem(SECTION_KEY);
    var topic = localStorage.getItem(TOPIC_KEY);
    var params = [];
    if (section) params.push("section=" + encodeURIComponent(section));
    if (topic) params.push("topic=" + encodeURIComponent(topic));
    if (params.length) {
      window.location.replace("/?" + params.join("&"));
    }
  }
})();

// Research side panel - EDITION-AND-UI.md Part 3. Rule 4: nothing here
// runs until the reader explicitly clicks - opening the panel, a starter
// question, Ask/Timeline/Explain are all click-triggered, never on load.
(function () {
  var article = document.querySelector(".article-full[data-url-hash]");
  var panel = document.getElementById("research-panel");
  var layout = document.querySelector(".article-layout");
  if (!article || !panel || !layout) return;

  var hash = article.dataset.urlHash;
  var WIDTH_KEY = "aakasavani:panel-width";

  var openBtn = document.getElementById("research-open");
  var closeBtn = document.getElementById("research-close");

  function applyStoredWidth() {
    var w = localStorage.getItem(WIDTH_KEY);
    if (w) panel.style.width = w + "px";
  }

  function openPanel() {
    layout.classList.add("panel-open");
    document.body.classList.add("panel-open");
    panel.setAttribute("aria-hidden", "false");
    applyStoredWidth();
    loadStarterQuestionsOnce();
  }

  function closePanel() {
    layout.classList.remove("panel-open");
    document.body.classList.remove("panel-open");
    panel.setAttribute("aria-hidden", "true");
  }

  if (openBtn) openBtn.addEventListener("click", openPanel);
  if (closeBtn) closeBtn.addEventListener("click", closePanel);

  // Tabs.
  var tabButtons = panel.querySelectorAll("[data-tab]");
  var tabPanels = panel.querySelectorAll("[data-tab-panel]");
  for (var t = 0; t < tabButtons.length; t++) {
    tabButtons[t].addEventListener("click", function () {
      var chosen = this.dataset.tab;
      for (var a = 0; a < tabButtons.length; a++) {
        tabButtons[a].classList.toggle("active", tabButtons[a] === this);
      }
      for (var b = 0; b < tabPanels.length; b++) {
        tabPanels[b].hidden = tabPanels[b].dataset.tabPanel !== chosen;
      }
      if (chosen === "timeline") loadTimelineOnce();
    });
  }

  // ── Ask tab ──────────────────────────────────────────────────────────
  var questionsLoaded = false;
  function loadStarterQuestionsOnce() {
    if (questionsLoaded) return;
    questionsLoaded = true;
    var box = document.getElementById("starter-questions");
    box.textContent = "Loading questions...";
    fetch("/research/" + hash + "/starter-questions")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        box.innerHTML = "";
        if (data.error) {
          box.textContent = data.error;
          return;
        }
        var questions = data.questions || [];
        if (!questions.length) {
          box.textContent = "";
          return;
        }
        questions.forEach(function (q) {
          var b = document.createElement("button");
          b.type = "button";
          b.className = "starter-question";
          b.textContent = q;
          b.addEventListener("click", function () { askQuestion(q); });
          box.appendChild(b);
        });
      })
      .catch(function () {
        box.textContent = "Couldn't load questions right now.";
      });
  }

  var askForm = document.getElementById("ask-form");
  var askInput = document.getElementById("ask-input");
  var askAnswer = document.getElementById("ask-answer");

  function askQuestion(question) {
    askAnswer.textContent = "Thinking...";
    fetch("/research/" + hash + "/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) {
          askAnswer.textContent = data.error;
          return;
        }
        askAnswer.textContent = data.text || "";
      })
      .catch(function () {
        askAnswer.textContent = "Couldn't reach the research panel right now.";
      });
  }

  if (askForm) {
    askForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var q = askInput.value.trim();
      if (!q) return;
      askQuestion(q);
      askInput.value = "";
    });
  }

  var summariseBtn = document.getElementById("summarise-btn");
  if (summariseBtn) {
    summariseBtn.addEventListener("click", function () {
      askQuestion("Summarise this article.");
    });
  }

  // ── Timeline tab ─────────────────────────────────────────────────────
  var timelineLoaded = false;
  function loadTimelineOnce() {
    if (timelineLoaded) return;
    timelineLoaded = true;
    var box = document.getElementById("timeline-results");
    box.textContent = "Loading timeline...";
    var heading = article.querySelector("h1");
    var title = heading ? heading.textContent : "";
    fetch("/research/" + hash + "/timeline?query=" + encodeURIComponent(title))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        box.innerHTML = "";
        if (data.error) {
          box.textContent = data.error;
          return;
        }
        var entries = data.entries || [];
        if (!entries.length) {
          box.textContent = "No timeline available for this story.";
          return;
        }
        entries.forEach(function (entry) {
          var row = document.createElement("a");
          row.className = "timeline-entry";
          row.href = entry.url;
          row.target = "_blank";
          row.rel = "noopener";
          var date = document.createElement("span");
          date.className = "timeline-date";
          date.textContent = entry.date;
          var source = document.createElement("span");
          source.className = "timeline-source";
          source.textContent = " (" + entry.source + ")";
          row.appendChild(date);
          row.appendChild(document.createTextNode(" " + entry.title));
          row.appendChild(source);
          box.appendChild(row);
        });
      })
      .catch(function () {
        box.textContent = "Couldn't load the timeline right now.";
      });
  }

  // ── Explain tab ──────────────────────────────────────────────────────
  // Sends ONLY window.getSelection()'s text, read fresh at click time -
  // never the article's own stored body (EDITION-AND-UI.md §3.2, §3.5).
  var explainBtn = document.getElementById("explain-btn");
  var explainResult = document.getElementById("explain-result");

  if (explainBtn) {
    explainBtn.addEventListener("click", function () {
      var sel = window.getSelection();
      var selection = sel ? sel.toString().trim() : "";
      if (!selection) {
        explainResult.textContent = "Highlight some article text first, then click Explain.";
        return;
      }
      explainResult.textContent = "Explaining...";
      fetch("/research/" + hash + "/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selection: selection }),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.error) {
            explainResult.textContent = data.error;
            return;
          }
          explainResult.textContent = data.explanation || "";
        })
        .catch(function () {
          explainResult.textContent = "Couldn't reach the research panel right now.";
        });
    });
  }

  // ── Resizable panel - EDITION-AND-UI.md §3.1: "Resizable, width
  // remembered." ────────────────────────────────────────────────────────
  var handle = document.getElementById("panel-resize-handle");
  if (handle) {
    var dragging = false;
    handle.addEventListener("mousedown", function (e) {
      dragging = true;
      e.preventDefault();
    });
    document.addEventListener("mousemove", function (e) {
      if (!dragging) return;
      var newWidth = window.innerWidth - e.clientX;
      newWidth = Math.max(280, Math.min(newWidth, window.innerWidth * 0.7));
      panel.style.width = newWidth + "px";
    });
    document.addEventListener("mouseup", function () {
      if (!dragging) return;
      dragging = false;
      localStorage.setItem(WIDTH_KEY, parseInt(panel.style.width, 10));
    });
  }
})();
