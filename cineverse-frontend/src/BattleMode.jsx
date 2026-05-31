import React, { useState, useEffect, useRef } from 'react';
import './BattleMode.css';
import { moviesData } from './moviesData';

const CATEGORIES = [
    { id: "picture", label: "Best Picture", prompt: "Which is the better film overall?", icon: "🏆" },
    { id: "cinematography", label: "Best Cinematography", prompt: "Which has the more striking visual language?", icon: "📷" },
    { id: "direction", label: "Best Direction", prompt: "Whose directorial vision wins?", icon: "🎬" },
    { id: "score", label: "Best Score & Sound", prompt: "Which one's music gets under your skin?", icon: "🎵" },
    { id: "story", label: "Best Story", prompt: "Which screenplay holds together better?", icon: "📖" },
    { id: "legacy", label: "Cultural Legacy", prompt: "Which film will still matter in 50 years?", icon: "🌍" },
    { id: "cast", label: "Best Cast", prompt: "Whose performances stay with you?", icon: "🎭" },
];

const HOW_STEPS = [
    { n: "01", title: "Pick your fighters", desc: "Search any two films — or hit Surprise Me and let the arena handpick a juicy matchup.", icon: "🔍", color: "#22d3ee" },
    { n: "02", title: "Vote category by category", desc: "Best Picture, Cinematography, Score, Story, Direction, Cast, Legacy. Add your reasoning for each.", icon: "🗳️", color: "#fb923c" },
    { n: "03", title: "CineBot crowns the winner", desc: "Your votes meet real audience data. CineBot delivers a decisive cinematic verdict on who reigns.", icon: "👑", color: "#e9b949" },
];

const allMovies = (() => {
    const seen = new Set(); const list = [];
    for (const mood of Object.values(moviesData))
        for (const m of mood.movies)
            if (!seen.has(m.title)) { seen.add(m.title); list.push(m); }
    return list;
})();

export default function BattleMode() {
    const [step, setStep] = useState("home");
    const [movieA, setMovieA] = useState(null);
    const [movieB, setMovieB] = useState(null);
    const [searchA, setSearchA] = useState("");
    const [searchB, setSearchB] = useState("");
    const [openA, setOpenA] = useState(false);
    const [openB, setOpenB] = useState(false);
    const [resultsA, setResultsA] = useState([]);
    const [resultsB, setResultsB] = useState([]);
    const [votes, setVotes] = useState({});
    const [verdict, setVerdict] = useState("");
    const [scores, setScores] = useState({});
    const [winner, setWinner] = useState(null);
    const [showWhy, setShowWhy] = useState({});

    const refA = useRef(null);
    const refB = useRef(null);
    const howRef = useRef(null);
    const timerA = useRef(null);
    const timerB = useRef(null);

    useEffect(() => {
        const h = (e) => {
            if (refA.current && !refA.current.contains(e.target)) setOpenA(false);
            if (refB.current && !refB.current.contains(e.target)) setOpenB(false);
        };
        document.addEventListener("mousedown", h);
        return () => document.removeEventListener("mousedown", h);
    }, []);

    // Levenshtein distance for typo tolerance
    const lev = (a, b) => {
        a = a.toLowerCase(); b = b.toLowerCase();
        const dp = Array.from({ length: a.length + 1 }, (_, i) =>
            Array.from({ length: b.length + 1 }, (_, j) => i === 0 ? j : j === 0 ? i : 0));
        for (let i = 1; i <= a.length; i++)
            for (let j = 1; j <= b.length; j++)
                dp[i][j] = a[i - 1] === b[j - 1] ? dp[i - 1][j - 1]
                    : 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
        return dp[a.length][b.length];
    };

    // Token fuzzy scorer — higher = better match
    const fuzzyScore = (query, title) => {
        const q = query.toLowerCase().trim();
        const t = title.toLowerCase();
        if (t === q) return 100;
        if (t.startsWith(q)) return 90;
        if (t.includes(q)) return 80;
        const qWords = q.split(/\s+/); const tWords = t.split(/\s+/);
        let hits = 0;
        for (const qw of qWords) {
            if (tWords.some(tw => tw === qw)) { hits += 10; continue; }
            if (tWords.some(tw => tw.startsWith(qw) || qw.startsWith(tw))) { hits += 6; continue; }
            if (tWords.some(tw => lev(qw, tw) <= Math.floor(qw.length / 3) + 1)) hits += 3;
        }
        return hits;
    };

    // Fuzzy local fallback (when Flask is offline)
    const fuzzyLocalSearch = (query) =>
        allMovies
            .map(m => ({ m, score: fuzzyScore(query, m.title) }))
            .filter(({ score }) => score > 0)
            .sort((a, b) => b.score - a.score)
            .slice(0, 8)
            .map(({ m }) => ({
                title: m.title, year: String(m.year || ''), rating: m.rating,
                img: m.img ? `/images/${m.img.replace(/^images\//, '')}` : null,
            }));

    const searchTMDB = (query, setter, openSetter) => {
        if (query.length < 2) { setter([]); return; }
        const q = query.trim();
        fetch(`http://127.0.0.1:5000/api/search?q=${encodeURIComponent(q)}`)
            .then(r => { if (!r.ok) throw new Error('bad'); return r.json(); })
            .then(d => {
                let items = (d.results || [])
                    .filter(m => m.title)
                    .map(m => ({
                        title: m.title,
                        year: m.release_date ? m.release_date.slice(0, 4) : '',
                        rating: m.rating,
                        img: m.poster_url || null,   // full TMDB poster URL
                    }));
                // Re-rank by how closely the query matches (puts exact hits first)
                items.sort((a, b) => fuzzyScore(q, b.title) - fuzzyScore(q, a.title));
                items = items.slice(0, 8);
                if (items.length > 0) {
                    setter(items); openSetter(true);
                } else {
                    // TMDB returned nothing (bad spelling) — use local fuzzy
                    const local = fuzzyLocalSearch(q);
                    setter(local); if (local.length) openSetter(true);
                }
            })
            .catch(() => {
                // Flask offline — full local fuzzy search with Levenshtein
                const local = fuzzyLocalSearch(q);
                setter(local); if (local.length) openSetter(true);
            });
    };

    // After pick, fetch TMDB poster if the movie has no real img URL
    const enrichWithPoster = async (movie, setter) => {
        if (movie.img && movie.img.startsWith('http')) return; // already has real poster
        try {
            const r = await fetch(`http://127.0.0.1:5000/api/search?q=${encodeURIComponent(movie.title)}`);
            const d = await r.json();
            const match = (d.results || []).find(m => m.title?.toLowerCase() === movie.title.toLowerCase());
            if (match?.poster_url) setter(prev => prev ? { ...prev, img: match.poster_url } : prev);
        } catch { /* Flask offline — keep placeholder */ }
    };

    const pickA = (m) => {
        setMovieA(m); setSearchA(""); setOpenA(false); setResultsA([]);
        enrichWithPoster(m, setMovieA);
    };
    const pickB = (m) => {
        setMovieB(m); setSearchB(""); setOpenB(false); setResultsB([]);
        enrichWithPoster(m, setMovieB);
    };

    const handleSurprise = async () => {
        setSearchA(""); setSearchB(""); setOpenA(false); setOpenB(false);
        try {
            const r = await fetch("http://127.0.0.1:5000/api/random_movies");
            if (!r.ok) throw new Error();
            const d = await r.json();
            if (d.results && d.results.length >= 2) {
                const mapTMDB = (m) => ({
                    title: m.title,
                    year: m.release_date ? m.release_date.slice(0, 4) : '',
                    rating: m.rating,
                    img: m.poster_url || null
                });
                setMovieA(mapTMDB(d.results[0]));
                setMovieB(mapTMDB(d.results[1]));
            } else {
                throw new Error("Not enough movies");
            }
        } catch {
            const shuffled = [...allMovies].sort(() => Math.random() - 0.5);
            setMovieA(shuffled[0]); setMovieB(shuffled[1]);
        }
    };

    const castVote = (catId, side) => {
        setVotes(prev => ({ ...prev, [catId]: { ...prev[catId], pick: prev[catId]?.pick === side ? null : side } }));
    };
    const skipVote = (catId) => {
        setVotes(prev => ({ ...prev, [catId]: { pick: 'skip', reasoning: '' } }));
    };
    const setReason = (catId, text) => {
        setVotes(prev => ({ ...prev, [catId]: { ...prev[catId], reasoning: text } }));
    };
    const toggleWhy = (catId) => setShowWhy(prev => ({ ...prev, [catId]: !prev[catId] }));

    const numVoted = CATEGORIES.filter(c => votes[c.id]?.pick).length;

    const poster = (m) => {
        if (!m?.img) return null;
        if (m.img.startsWith('http')) return m.img;
        return `/images/${m.img.replace(/^images\//, '')}`;
    };

    const scrollToHow = () => howRef.current?.scrollIntoView({ behavior: "smooth" });

    const ignite = async () => {
        setStep("loading");
        let aWins = 0, bWins = 0;
        let breakdown = "";
        const catScores = {};

        const CAT_MOD = {
            picture: { a: 0, b: 0 },
            cinematography: { a: 0.1, b: -0.1 },
            direction: { a: 0.05, b: 0.05 },
            score: { a: -0.1, b: 0.2 },
            story: { a: 0.15, b: -0.05 },
            legacy: { a: 0, b: 0.1 },
            cast: { a: 0.05, b: 0 },
        };

        CATEGORIES.forEach(cat => {
            const v = votes[cat.id];
            const baseA = parseFloat(movieA.rating) || 7.0;
            const baseB = parseFloat(movieB.rating) || 7.0;
            const mod = CAT_MOD[cat.id] || { a: 0, b: 0 };
            const rand = () => (Math.random() * 0.6) - 0.3;
            let sA = Math.min(10, Math.max(1, baseA + mod.a + rand()));
            let sB = Math.min(10, Math.max(1, baseB + mod.b + rand()));
            if (v?.pick === 'a') sA = Math.min(10, sA + 0.6);
            else if (v?.pick === 'b') sB = Math.min(10, sB + 0.6);
            sA = parseFloat(sA.toFixed(1)); sB = parseFloat(sB.toFixed(1));
            if (sA >= sB) aWins++; else bWins++;
            catScores[cat.id] = { a: sA, b: sB, reasoning: v?.reasoning || '', pick: v?.pick };
            if (v?.pick && v.pick !== 'skip') breakdown += `- ${cat.label}: ${sA >= sB ? movieA.title : movieB.title} (${sA} vs ${sB})${v.reasoning ? ` | "${v.reasoning}"` : ''}\n`;
        });

        setScores(catScores);
        const w = aWins >= bWins ? movieA : movieB;
        setWinner(w);

        try {
            const prompt = `Two films competed: "${movieA.title}" vs "${movieB.title}".\nVotes:\n${breakdown}\nAs CineBot, write a punchy 2-3 sentence verdict crowning ${w.title} as the winner. Be witty and decisive.`;
            const res = await fetch("http://127.0.0.1:5000/api/cinebot", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: prompt, history: [] })
            });
            if (res.ok) { const d = await res.json(); setVerdict(d.reply.replace(/\*\*/g, "")); }
            else throw new Error();
        } catch {
            setVerdict(`CineBot crowns "${w.title}" the undisputed champion — winning ${Math.max(aWins, bWins)} of ${CATEGORIES.length} categories. The verdict is final.`);
        }
        setStep("verdict");
    };

    const Nav = () => (
        <header className="bm-nav">
            <a href="/" className="bm-logo">CINEVERSE</a>
            <nav className="bm-navlinks">
                <a href="http://127.0.0.1:5500/Home_Page/index_home.html">HOME</a>
                <a href="/">MOODMATCHER</a>
                <a href="/battle">CINE BATTLE</a>
                <a href="http://127.0.0.1:5500/Home_Page/Movies.html">MOVIES</a>
                <a href="http://127.0.0.1:5500/Home_Page/chat.html">CHATBOT</a>
                <a href="http://127.0.0.1:5500/Home_Page/about.html">ABOUT</a>
                <a href="http://127.0.0.1:5500/Home_Page/Contact.html">CONTACT</a>
            </nav>
            <a href="/battle" className="bm-battle-pill">⚔ BATTLE</a>
        </header>
    );

    const ArenaBadge = () => (
        <div className="bm-arena-badge">
            <span className="bm-badge-line" />⚔ CINEBOT BATTLE ARENA ⚔<span className="bm-badge-line" />
        </div>
    );

    if (step === "home") return (
        <div className="bm-body">
            <div className="bm-hero">
                <Nav />
                <div className="bm-hero-inner">
                    <ArenaBadge />
                    <h1 className="bm-headline">
                        Two films enter.<br />
                        <em className="bm-headline-gold">One legend leaves.</em>
                    </h1>
                    <p className="bm-subtext">
                        You decide. Then CineBot crowns. Vote category by category, speak your case out loud, and walk away with a trophy poster worth sharing.
                    </p>
                    <div className="bm-hero-btns">
                        <button className="bm-btn-gold" onClick={() => setStep("select")}>⚔ START A BATTLE →</button>
                        <button className="bm-btn-outline" onClick={scrollToHow}>↓ HOW IT WORKS</button>
                    </div>

                    <div className="bm-scroll-hint">
                        <span className="bm-scroll-label">SCROLL</span>
                        <div className="bm-scroll-line" />
                    </div>
                </div>
            </div>

            <section className="bm-how" ref={howRef}>
                <div className="bm-how-header">
                    <div className="bm-arena-badge"><span className="bm-badge-line" />✦ THE PROCESS ✦<span className="bm-badge-line" /></div>
                    <h2 className="bm-how-title">How the arena works</h2>
                    <p className="bm-how-sub">Pick your fighters, judge them like a critic, and let CineBot deliver the verdict.</p>
                </div>
                <div className="bm-how-grid">
                    {HOW_STEPS.map(s => {
                        const colorKey = s.color === '#22d3ee' ? 'cyan' : s.color === '#fb923c' ? 'amber' : 'gold';
                        return (
                            <div key={s.n} className="bm-how-card" data-color={colorKey}>
                                <div className="bm-how-num" style={{ color: s.color }}>{s.n}</div>
                                <div className="bm-how-icon" style={{ color: s.color, borderColor: s.color, boxShadow: `0 0 24px -8px ${s.color}` }}>{s.icon}</div>
                                <div className="bm-how-step" style={{ color: s.color }}>STEP {s.n}</div>
                                <h3 className="bm-how-card-title">{s.title}</h3>
                                <p className="bm-how-card-desc">{s.desc}</p>
                            </div>
                        );
                    })}
                </div>
                <div style={{ textAlign: 'center', marginTop: '48px' }}>
                    <button className="bm-btn-gold" onClick={() => setStep("select")}>✦ ENTER THE ARENA →</button>
                </div>
            </section>

            <footer className="bm-footer">CINEVERSE · WHERE FILMS FIGHT</footer>
        </div>
    );

    if (step === "select") return (
        <div className="bm-body bm-dark">
            <div className="bm-dark-bg" />
            <Nav />
            <div className="bm-select-hero">
                <ArenaBadge />
                <h1 className="bm-headline-sm">
                    You decide.<br />
                    <span className="bm-headline-muted">Then CineBot crowns.</span>
                </h1>
                <p className="bm-subtext" style={{ marginTop: '12px' }}>
                    Pick two films — or let CineBot surprise you. Vote across seven categories and walk away with the verdict.
                </p>
                <div className="bm-hero-btns" style={{ marginTop: '28px' }}>
                    <button className="bm-btn-outline bm-sm" onClick={() => setStep("select")}>🔍 I'LL PICK</button>
                    <button className="bm-btn-outline bm-sm" onClick={handleSurprise}>🔀 SURPRISE ME</button>
                </div>
            </div>

            <div className="bm-fighters">
                <div className="bm-fighter-wrap" ref={refA}>
                    <div className="bm-fighter-label bm-label-a">FIGHTER ONE</div>
                    {movieA ? (
                        <div className="bm-poster-card bm-card-a">
                            <button className="bm-clear" onClick={() => setMovieA(null)}>✕</button>
                            {poster(movieA) ? <img src={poster(movieA)} className="bm-poster-img" alt={movieA.title} /> : <div className="bm-no-poster">🎬</div>}
                            <div className="bm-poster-foot">
                                <div className="bm-poster-title">{movieA.title}</div>
                                <div className="bm-poster-meta">{movieA.year}{movieA.rating ? ` ⭐ ${movieA.rating}` : ""}</div>
                            </div>
                        </div>
                    ) : (
                        <div className="bm-empty-card bm-empty-a">
                            <div className="bm-search-wrap">
                                <span className="bm-search-icon">🔍</span>
                                <input
                                    className="bm-search-input bm-input-a"
                                    placeholder="Search any film (1950–2026)..."
                                    value={searchA}
                                    onChange={e => {
                                        const val = e.target.value;  // capture before event pool clears
                                        setSearchA(val);
                                        clearTimeout(timerA.current);
                                        timerA.current = setTimeout(() => searchTMDB(val, setResultsA, setOpenA), 350);
                                    }}
                                    onFocus={() => resultsA.length && setOpenA(true)}
                                    autoComplete="off"
                                />{openA && resultsA.length > 0 && (
                                    <ul className="bm-dropdown">
                                        {resultsA.map(m => (
                                            <li key={m.title + m.year} className="bm-dd-item" onClick={() => pickA(m)}>
                                                {m.img
                                                    ? <img src={m.img} className="bm-dd-thumb" alt="" />
                                                    : <div className="bm-dd-no-thumb">🎬</div>
                                                }
                                                <div className="bm-dd-info">
                                                    <span className="bm-dd-title">{m.title}</span>
                                                    <span className="bm-dd-year">{m.year}{m.rating ? ` • ★ ${m.rating}` : ''}</span>
                                                </div>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                            <div className="bm-awaiting">🎬 Awaiting challenger</div>
                        </div>
                    )}
                </div>

                <div className="bm-vs-wrap">
                    <div className="bm-vs-badge"><span className="bm-vs-text">VS</span></div>
                    {movieA && movieB && (
                        <button className="bm-reroll" onClick={handleSurprise}>🔀 Reroll</button>
                    )}
                </div>

                <div className="bm-fighter-wrap" ref={refB}>
                    <div className="bm-fighter-label bm-label-b">FIGHTER TWO</div>
                    {movieB ? (
                        <div className="bm-poster-card bm-card-b">
                            <button className="bm-clear" onClick={() => setMovieB(null)}>✕</button>
                            {poster(movieB) ? <img src={poster(movieB)} className="bm-poster-img" alt={movieB.title} /> : <div className="bm-no-poster">🎬</div>}
                            <div className="bm-poster-foot">
                                <div className="bm-poster-title">{movieB.title}</div>
                                <div className="bm-poster-meta">{movieB.year}{movieB.rating ? ` ⭐ ${movieB.rating}` : ""}</div>
                            </div>
                        </div>
                    ) : (
                        <div className="bm-empty-card bm-empty-b">
                            <div className="bm-search-wrap">
                                <span className="bm-search-icon">🔍</span>
                                <input
                                    className="bm-search-input bm-input-b"
                                    placeholder="Search any film (1950–2026)..."
                                    value={searchB}
                                    onChange={e => {
                                        const val = e.target.value;  // capture before event pool clears
                                        setSearchB(val);
                                        clearTimeout(timerB.current);
                                        timerB.current = setTimeout(() => searchTMDB(val, setResultsB, setOpenB), 350);
                                    }}
                                    onFocus={() => resultsB.length && setOpenB(true)}
                                    autoComplete="off"
                                />{openB && resultsB.length > 0 && (
                                    <ul className="bm-dropdown">
                                        {resultsB.map(m => (
                                            <li key={m.title + m.year} className="bm-dd-item" onClick={() => pickB(m)}>
                                                {m.img
                                                    ? <img src={m.img} className="bm-dd-thumb" alt="" />
                                                    : <div className="bm-dd-no-thumb">🎬</div>
                                                }
                                                <div className="bm-dd-info">
                                                    <span className="bm-dd-title">{m.title}</span>
                                                    <span className="bm-dd-year">{m.year}{m.rating ? ` • ★ ${m.rating}` : ''}</span>
                                                </div>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                            <div className="bm-awaiting">🎬 Awaiting challenger</div>
                        </div>
                    )}
                </div>
            </div>

            <div className="bm-enter-wrap">
                {movieA && movieB
                    ? <button className="bm-btn-enter" onClick={() => { setVotes({}); setStep("vote"); }}>⚔ ENTER THE VOTING ROOM</button>
                    : <p className="bm-select-hint">Select both fighters to proceed</p>
                }
            </div>
        </div>
    );

    /* ──────────── VOTE ──────────── */
    if (step === "vote") return (
        <div className="bm-body bm-dark">
            <div className="bm-dark-bg" />
            <Nav />
            <div className="bm-vote-header">
                <p className="bm-vote-instructions">
                    Pick a winner per category. Add written reasoning if you want — CineBot will weigh your case.{" "}
                    <em className="bm-vote-count">{numVoted}/7 voted</em>
                </p>
            </div>
            <div className="bm-vote-grid">
                {CATEGORIES.map(cat => {
                    const vote = votes[cat.id];
                    const pickedA = vote?.pick === "a";
                    const pickedB = vote?.pick === "b";
                    return (
                        <div key={cat.id} className="bm-vote-card">
                            <div className="bm-vote-cat-header">
                                <span className="bm-cat-icon">{cat.icon}</span>
                                <span className="bm-cat-label">{cat.label}</span>
                            </div>
                            <div className="bm-cat-prompt">{cat.prompt}</div>
                            <div className="bm-pick-row">
                                <button className={`bm-pick-card ${pickedA ? "bm-pick-a" : ""}`} onClick={() => castVote(cat.id, "a")}>
                                    {poster(movieA) ? <img src={poster(movieA)} className="bm-pick-thumb" alt="" /> : <div className="bm-pick-nothumb">🎬</div>}
                                    <div className="bm-pick-info">
                                        <div className="bm-pick-title">{movieA.title}</div>
                                        <div className="bm-pick-year">{movieA.year}</div>
                                    </div>
                                    {pickedA && <div className="bm-crown-a">👑</div>}
                                </button>
                                <span className="bm-vs-mini">VS</span>
                                <button className={`bm-pick-card ${pickedB ? "bm-pick-b" : ""}`} onClick={() => castVote(cat.id, "b")}>
                                    {poster(movieB) ? <img src={poster(movieB)} className="bm-pick-thumb" alt="" /> : <div className="bm-pick-nothumb">🎬</div>}
                                    <div className="bm-pick-info">
                                        <div className="bm-pick-title">{movieB.title}</div>
                                        <div className="bm-pick-year">{movieB.year}</div>
                                    </div>
                                    {pickedB && <div className="bm-crown-b">👑</div>}
                                </button>
                            </div>
                            <div className="bm-vote-actions">
                                <button className="bm-add-why" onClick={() => toggleWhy(cat.id)}>
                                    ✎ {showWhy[cat.id] ? "Hide" : "Add reasoning"}
                                </button>
                                <button className={`bm-skip-btn ${vote?.pick === 'skip' ? 'bm-skip-active' : ''}`} onClick={() => skipVote(cat.id)}>
                                    ↷ Skip vote
                                </button>
                            </div>
                            {showWhy[cat.id] && (
                                <textarea className="bm-why-input" placeholder="Why this film wins this round..." rows={3}
                                    value={vote?.reasoning || ""} onChange={e => setReason(cat.id, e.target.value)} />
                            )}
                        </div>
                    );
                })}
            </div>
            <div className="bm-ignite-wrap">
                {numVoted < 7 && <p className="bm-ignite-hint">{7 - numVoted} more {7 - numVoted === 1 ? "category" : "categories"} to vote (or skip)</p>}
                <button className="bm-btn-enter" onClick={ignite} disabled={numVoted < 7} style={{ opacity: numVoted < 7 ? 0.45 : 1 }}>
                    ⚡ IGNITE THE BATTLE
                </button>
            </div>
        </div>
    );

    /* ──────────── LOADING ──────────── */
    if (step === "loading") return (
        <div className="bm-body bm-dark bm-loading-screen">
            <div className="bm-dark-bg" />
            <Nav />
            <div className="bm-loading-inner">
                <div className="bm-loading-spinner" />
                <h2 className="bm-loading-title">CINEBOT IS WEIGHING THE EVIDENCE</h2>
                <p className="bm-loading-sub">Analysing your votes and cross-referencing cinematic data…</p>
            </div>
        </div>
    );

    /* ──────────── VERDICT ──────────── */
    if (step === "verdict" && winner) {
        const loser = winner.title === movieA.title ? movieB : movieA;
        
        // Calculate user overall win/loss
        const userA = CATEGORIES.filter(c => votes[c.id]?.pick === 'a').length;
        const userB = CATEGORIES.filter(c => votes[c.id]?.pick === 'b').length;
        const userWinner = userA > userB ? movieA : (userB > userA ? movieB : null);
        const userCorrect = userWinner?.title === winner.title;

        return (
            <div className="bm-body bm-dark">
                <div className="bm-dark-bg" />
                <Nav />
                <div className="bm-verdict-wrap">
                    <ArenaBadge />
                    <div className="bm-champion-label">👑 CHAMPION</div>
                    <h1 className="bm-champion-name">{winner.title}</h1>

                    {/* Posters */}
                    <div className="bm-verdict-posters">
                        <div className="bm-vp-winner">
                            {poster(winner) && <img src={poster(winner)} className="bm-vp-img-win" alt={winner.title} />}
                            <div className="bm-vp-caption-win">WINNER</div>
                        </div>
                        <div className="bm-vp-loser">
                            {poster(loser) && <img src={poster(loser)} className="bm-vp-img-lose" alt={loser.title} />}
                            <div className="bm-vp-caption-lose">DEFEATED</div>
                        </div>
                    </div>

                    {/* User Overall Result */}
                    {userWinner && (
                        <div className={`bm-user-result ${userCorrect ? 'bm-user-win' : 'bm-user-loss'}`}>
                            {userCorrect 
                                ? "🏆 YOU CHOSE CORRECTLY! YOUR CHAMPION WON." 
                                : "💀 YOU WERE DEFEATED! CINEBOT DISAGREES WITH YOUR PICKS."}
                        </div>
                    )}

                    {/* CineBot verdict quote */}
                    <div className="bm-verdict-text"><p>"{verdict}"</p></div>

                    {/* Category score breakdown */}
                    <div className="bm-score-breakdown">
                        {CATEGORIES.map(cat => {
                            const s = scores[cat.id] || { a: 7, b: 7, reasoning: "", pick: null };
                            const winnerCat = s.a > s.b ? "a" : (s.b > s.a ? "b" : "tie");
                            
                            // Check if user's pick matched the AI winner for this category
                            let statusClass = "";
                            if (s.pick === 'a' || s.pick === 'b') {
                                statusClass = s.pick === winnerCat ? "bm-correct" : "bm-incorrect";
                            }

                            return (
                                <div key={cat.id} className={`bm-score-card ${statusClass}`}>
                                    <div className="bm-score-card-header">
                                        <div className="bm-vote-cat-header">
                                            <span className="bm-cat-icon">{cat.icon}</span>
                                            <span className="bm-cat-label">{cat.label}</span>
                                        </div>
                                        {winnerCat !== "tie" && (
                                            <div className={`bm-round-badge ${winnerCat === "a" ? "bm-round-a" : "bm-round-b"}`}>
                                                ROUND → {winnerCat.toUpperCase()}
                                            </div>
                                        )}
                                    </div>
                                    <div className="bm-score-bars">
                                        <div className="bm-score-row">
                                            <span className="bm-score-name">{movieA.title}</span>
                                            <div className="bm-bar-wrap">
                                                <div className="bm-bar bm-bar-a" style={{ width: `${(s.a / 10) * 100}%` }} />
                                            </div>
                                            <span className="bm-score-val">{s.a}</span>
                                        </div>
                                        <div className="bm-score-row">
                                            <span className="bm-score-name">{movieB.title}</span>
                                            <div className="bm-bar-wrap">
                                                <div className="bm-bar bm-bar-b" style={{ width: `${(s.b / 10) * 100}%` }} />
                                            </div>
                                            <span className="bm-score-val">{s.b}</span>
                                        </div>
                                    </div>
                                    {s.reasoning && <p className="bm-score-reason">"{s.reasoning}"</p>}
                                </div>
                            );
                        })}
                    </div>

                    <div className="bm-verdict-btns">
                        <button className="bm-btn-enter" onClick={() => { setMovieA(null); setMovieB(null); setVotes({}); setWinner(null); setScores({}); setStep("select"); }}>⚔ NEW BATTLE</button>
                        <button className="bm-btn-outline" onClick={() => setStep("home")}>← HOME</button>
                    </div>
                </div>
            </div>
        );
    }

    return null;
}
