const IMG_BASE = "https://image.tmdb.org/t/p/";
const TMDB_API_KEY = "d4ded1dcd06236100cb440817a7363ae";
const BACKEND_API = "http://127.0.0.1:5000/api/cinebot";

let currentMovie = {};
let chatHistory = [];
let originalChartInstance = null;
let userChartInstance = null;
let emotionLoaded = false;  // guard: only draw once per page load

const pageMsg = document.getElementById("pageMessage");

document.addEventListener("DOMContentLoaded", async () => {
  const params = new URLSearchParams(location.search);
  const tmdbId = params.get("tmdb_id");
  const title = params.get("title");
  const year = params.get("year");

  const chatForm = document.getElementById("chatForm");
  if (chatForm) {
    chatForm.addEventListener("submit", handleChatSubmit);
  }

  const textarea = document.getElementById("userPrompt");
  if (textarea) {
    textarea.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        chatForm.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });
  }

  if (tmdbId) {
    await loadMovieById(tmdbId);
  } else if (title) {
    await loadMovieBySearch(title, year);
  } else {
    showError("No movie specified. Go back and select one.");
  }
});

// Helper for fetch with timeout
async function fetchWithTimeout(resource, options = {}) {
  const { timeout = 3000 } = options;
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  const response = await fetch(resource, {
    ...options,
    signal: controller.signal  
  });
  clearTimeout(id);
  return response;
}

async function loadMovieById(id) {
  try {
    const response = await fetchWithTimeout(`http://127.0.0.1:5000/api/movie/${id}`, { timeout: 4000 });
    if (!response.ok) {
      throw new Error(`Movie API request failed with ${response.status}`);
    }
    const movie = await response.json();
    if (movie.error || !movie.title) {
       throw new Error("TMDB Blocked");
    }
    populateMovie(movie);
    loadOriginalEmotion();  // backend gave us full data — draw graph now
  } catch (error) {
    console.error("Movie lookup failed via backend, trying cache:", error);
    await loadMovieFromCache(id, null, null);
  }
}

async function loadMovieFromCache(id, title, year) {
  try {
    const cacheRes = await fetch("movies_cache.json");
    const cache = await cacheRes.json();

    let found = null;
    if (id) {
      found = cache.find(m => String(m.tmdb_id) === String(id) || String(m.id) === String(id));
    }
    if (!found && title) {
      const titleLower = title.toLowerCase();
      found = cache.find(m => {
        const movieTitle = (m.title || m.name || "").toLowerCase();
        const movieYear  = m.release_date ? m.release_date.slice(0, 4) : "";
        return movieTitle === titleLower && (!year || year === "N/A" || movieYear === year);
      });
    }

    if (found) {
      // 1. Initial render (Title and basic info)
      populateMovie(found);

      // 2. If metadata is missing or generic, fetch the REAL story dynamically
      if (!found.director || found.director === "Unknown" || !found.genres || found.genres.length === 0) {
        console.log("Fetching detailed story data...");
        const dirEl = document.getElementById("movieDirector");
        if (dirEl) dirEl.textContent = "Fetching details...";
        
        try {
          const infoRes = await fetch("http://127.0.0.1:5000/api/movie_info", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
              title: found.title || found.name, 
              year: found.release_date ? found.release_date.slice(0, 4) : "" 
            })
          });
          if (infoRes.ok) {
            const info = await infoRes.json();
            found.director = info.director;
            found.genres = info.genres;
            found.overview = info.overview;
            populateMovie(found); // Update UI with real story
          }
        } catch (e) {
          console.error("Story fetch failed:", e);
        }
      }
      
      // 3. Draw the graph using the REAL story/genres
      await loadOriginalEmotion();
    } else {
      showError("Movie not found in cache.");
    }
  } catch (err) {
    showError("Could not load movie cache.");
  }
}




async function loadMovieBySearch(title, year) {
  try {
    const response = await fetchWithTimeout(
      `http://127.0.0.1:5000/api/search?q=${encodeURIComponent(title)}`, { timeout: 3000 }
    );
    if (!response.ok) {
      throw new Error(`Search API request failed with ${response.status}`);
    }

    const data = await response.json();
    const found = (data.results || []).find((movie) => {
      const movieYear = movie.release_date ? movie.release_date.slice(0, 4) : "";
      return !year || year === "N/A" || movieYear === year;
    });

    if (found) {
      await loadMovieById(found.tmdb_id || found.id);
      return;
    }
  } catch (error) {
    console.warn("Backend search fallback failed:", error);
  }

  // Fallback to cache if TMDB search blocked
  await loadMovieFromCache(null, title, year);
}

function populateMovie(movie) {
  const titleEl = document.getElementById("movieTitle");
  const yearEl = document.getElementById("movieYear");
  const directorEl = document.getElementById("movieDirector");
  const genresEl = document.getElementById("movieGenres");
  const overviewEl = document.getElementById("movieOverview");
  const posterEl = document.getElementById("moviePoster");
  const backdrop = document.getElementById("backdrop");

  const releaseDate = movie.release_date || "";
  const year = releaseDate ? releaseDate.slice(0, 4) : "";
  const genreList = Array.isArray(movie.genres)
    ? movie.genres.map((genre) => (typeof genre === "string" ? genre : genre.name)).filter(Boolean)
    : [];
  const genresText =
    genreList.join(", ") ||
    (Array.isArray(movie.genre_ids) ? movie.genre_ids.join(", ") : "") ||
    "N/A";
  
  let director = "Unknown";
  if (movie.credits && movie.credits.crew) {
    const dir = movie.credits.crew.find(c => c.job === "Director");
    if (dir) director = dir.name;
  } else if (movie.director) {
    director = movie.director;
  }
  
  const overview = movie.overview || "No synopsis available.";
  const posterUrl =
    movie.poster_url ||
    (movie.poster_path ? `${IMG_BASE}w500${movie.poster_path}` : "placeholder.jpg");
  const backdropUrl = movie.backdrop_url || (movie.backdrop_path ? `${IMG_BASE}w1280${movie.backdrop_path}` : "");

  if (titleEl) titleEl.textContent = movie.title || movie.name || "Untitled";
  if (yearEl) yearEl.textContent = year ? `(${year})` : "";
  if (directorEl) directorEl.textContent = director;
  if (genresEl) genresEl.textContent = genresText;
  if (overviewEl) overviewEl.textContent = overview;
  if (posterEl) {
    posterEl.src = posterUrl;
    posterEl.alt = `${movie.title || "Movie"} poster`;
  }
  if (backdrop && backdropUrl) {
    backdrop.style.backgroundImage = `url('${backdropUrl}')`;
  }

  currentMovie = {
    title: movie.title || movie.name || "Unknown",
    release_date: releaseDate,
    director,
    genres: genreList,
    overview,
  };
  // Note: loadOriginalEmotion() is NOT called here.
  // It is called explicitly AFTER enrichment so the graph
  // always has real genre data to work from.
}

function showError(message) {
  if (!pageMsg) return;
  pageMsg.textContent = message;
  pageMsg.style.display = "block";
}

async function analyzeEmotionViaBackend(text, genres) {
  try {
    const response = await fetch("http://127.0.0.1:5000/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, genres: genres || [] })
    });
    
    if (!response.ok) return null;
    const data = await response.json();
    return data;
  } catch (e) {
    console.error("Failed to parse emotion from Backend:", e);
    return null;
  }
}

async function loadOriginalEmotion() {
  const text = `Movie Title: ${currentMovie.title}. Synopsis: ${currentMovie.overview}`;
  const emotions = await analyzeEmotionViaBackend(text, currentMovie.genres);
  if (emotions) {
    drawOriginalGraph(emotions);
  }
}

async function askOllamaBackend(question, history) {
  const response = await fetch(BACKEND_API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: question,
      movie: currentMovie,
      history: history.slice(-20),
    }),
  });
  
  if (!response.ok) {
    throw new Error(`Backend API failed: ${response.status}`);
  }
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  
  return data.reply;
}

async function handleChatSubmit(event) {
  event.preventDefault();

  const textarea = document.getElementById("userPrompt");
  const prompt = textarea.value.trim();
  if (!prompt) return;

  appendChatMessage(prompt, "user");
  textarea.value = "";
  chatHistory.push({ role: "user", content: prompt });

  const typingEl = showTypingIndicator();

  try {
    const reply = await askOllamaBackend(prompt, chatHistory);

    removeTypingIndicator(typingEl);
    appendChatMessage(reply, "bot");
    chatHistory.push({ role: "assistant", content: reply });
    
    // Get emotion for this new scenario
    const combinedText = `User Prompt: ${prompt}\n\nChatbot Answer: ${reply}`;
    const scenarioEmotion = await analyzeEmotionViaBackend(combinedText, currentMovie.genres);
    if (scenarioEmotion) {
      const userGraphCard = document.getElementById("userGraphCard");
      if (userGraphCard) userGraphCard.style.display = "block";
      drawUserGraph(scenarioEmotion);
    }
  } catch (error) {
    removeTypingIndicator(typingEl);
    console.error("CineBot fetch error:", error);
    appendChatMessage(
      "Could not reach Backend. Please ensure your Python flask server is running on http://127.0.0.1:5000.",
      "bot"
    );
  }
}

function appendChatMessage(text, sender) {
  const container = document.getElementById("chatWindow");
  if (!container) return;

  const message = document.createElement("div");
  message.className = `chat-msg ${sender === "user" ? "user" : "bot"}`;

  if (sender === "bot") {
    message.innerHTML = formatBotMessage(text);
  } else {
    message.textContent = text;
  }

  container.appendChild(message);
  container.scrollTop = container.scrollHeight;
}

function formatBotMessage(text) {
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/\n\n/g, "</p><p>");
  html = html.replace(/\n/g, "<br>");
  html = html.replace(/(?:^|<br>)-\s+(.+?)(?=<br>|<\/p>|$)/g, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>");
  html = html.replace(/<\/ul>\s*<ul>/g, "");

  return `<p>${html}</p>`;
}

function showTypingIndicator() {
  const container = document.getElementById("chatWindow");
  if (!container) return null;

  const indicator = document.createElement("div");
  indicator.className = "chat-msg bot typing-indicator";
  indicator.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
  container.appendChild(indicator);
  container.scrollTop = container.scrollHeight;
  return indicator;
}

function removeTypingIndicator(indicator) {
  if (indicator && indicator.parentNode) {
    indicator.parentNode.removeChild(indicator);
  }
}

const EMOTIONS = ["Joy", "Sadness", "Fear", "Anger", "Surprise", "Disgust"];
const EMOTION_COLORS = ["#FFD700", "#4A90D9", "#9B59B6", "#E74C3C", "#F39C12", "#2ECC71"];

function drawOriginalGraph(emotionsObj) {
  const canvas = document.getElementById("originalGraph");
  if (!canvas || typeof Chart === "undefined") return;

  const values = EMOTIONS.map(e => emotionsObj[e.toLowerCase()] || emotionsObj[e] || 0);

  if (originalChartInstance) {
    originalChartInstance.destroy();
  }

  originalChartInstance = new Chart(canvas, {
    type: "radar",
    data: {
      labels: EMOTIONS,
      datasets: [
        {
          label: "Emotion Profile",
          data: values,
          backgroundColor: "rgba(255, 196, 0, 0.2)",
          borderColor: "#ffc400",
          pointBackgroundColor: EMOTION_COLORS,
          pointBorderColor: "#fff",
          pointRadius: 5,
        },
      ],
    },
    options: getGraphOptions()
  });
}

function drawUserGraph(emotionsObj) {
  const canvas = document.getElementById("userGraph");
  if (!canvas || typeof Chart === "undefined") return;

  const values = EMOTIONS.map(e => emotionsObj[e.toLowerCase()] || emotionsObj[e] || 0);

  if (userChartInstance) {
    userChartInstance.destroy();
  }

  userChartInstance = new Chart(canvas, {
    type: "radar",
    data: {
      labels: EMOTIONS,
      datasets: [
        {
          label: "Your Story Profile",
          data: values,
          backgroundColor: "rgba(0, 196, 255, 0.2)",
          borderColor: "#00c4ff",
          pointBackgroundColor: EMOTION_COLORS,
          pointBorderColor: "#fff",
          pointRadius: 5,
        },
      ],
    },
    options: getGraphOptions()
  });
}

function getGraphOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      r: {
        beginAtZero: true,
        max: 100,
        ticks: { color: "#888", backdropColor: "transparent" },
        grid: { color: "rgba(255,255,255,0.1)" },
        pointLabels: { color: "#ccc", font: { size: 13 } },
      },
    },
    plugins: {
      legend: { labels: { color: "#ccc" } },
    },
  };
}
