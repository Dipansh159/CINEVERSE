import "./MoodMatcher.css";
import { useState } from "react";
import { moviesData } from "./moviesData";

const emotions = [
    { name: "Joy", sub: "Joyful", img: "/images/joy.png", color: "joy" },
    { name: "Sadness", sub: "Sad", img: "/images/sadness.png", color: "sadness" },
    { name: "Anger", sub: "Angry", img: "/images/anger.png", color: "anger" },
    { name: "Fear", sub: "Scared", img: "/images/fear.png", color: "fear" },
    { name: "Disgust", sub: "Disgusted", img: "/images/disgust.png", color: "disgust" },
    { name: "Anxiety", sub: "Stressed", img: "/images/anxiety.png", color: "anxiety" },
];

export default function MoodMatcher() {
    const [selectedEmotion, setSelectedEmotion] = useState(null);
    const [loading, setLoading] = useState(false);
    const [showResults, setShowResults] = useState(false);

    const handleEmotionClick = (emotion) => {
        if (selectedEmotion === emotion.name && showResults) return;

        setSelectedEmotion(emotion.name);
        setLoading(true);
        setShowResults(false);

        // Simulate thinking time
        setTimeout(() => {
            setLoading(false);
            setShowResults(true);
        }, 2500);
    };

    const activeEmotionData = selectedEmotion ? moviesData[selectedEmotion] : null;

    return (
        <div className="mood-wrapper" style={{ '--theme-color': activeEmotionData ? activeEmotionData.themeColor : '#facc15' }}>

            {/* GLOBAL NAVBAR */}
            <nav className="global-navbar">
                <a href="http://127.0.0.1:5500/Home_Page/index_home.html">Home</a>
                <a href="#" className="active">MoodMatcher</a>
                <a href="http://127.0.0.1:5500/Home_Page/about.html">About</a>
                <a href="http://127.0.0.1:5500/Home_Page/chat.html">Chatbot</a>
                <a href="http://127.0.0.1:5500/Home_Page/Movies.html">Movies</a>
                <a href="http://127.0.0.1:5500/Home_Page/Contact.html">Contact</a>
            </nav>

            <div className="logo">
                <div className="logo-box">
                    <img src="/images/icon.png" alt="logo" />
                </div>
                <span className="logo-text">CINEVERSE</span>
            </div>

            <h1 className="title">
                How are you <span>feeling?</span>
            </h1>

            <p className="subtitle">
                Let your emotion guide tonight's film. CineBot reads your mood and recommends the perfect stories.
            </p>

            <div className="powered">
                <span className="heartbeat-star">✨</span> POWERED BY CINEBOT AI
            </div>

            <div className="choose-emotion">
                — CHOOSE YOUR EMOTION —
            </div>

            {/* ✅ OUTER WRAPPER FOR PERFECT CENTERING */}
            <div className="cards-outer">
                <div className="cards-container">
                    <div className="cards">
                        {emotions.map((emotion) => {
                            const isActive = selectedEmotion === emotion.name;
                            return (
                                <div
                                    key={emotion.name}
                                    className={`card ${isActive ? 'active-card' : ''}`}
                                    onClick={() => handleEmotionClick(emotion)}
                                    style={isActive ? {
                                        '--card-color': activeEmotionData.themeColor,
                                        borderColor: activeEmotionData.themeColor,
                                        boxShadow: `0 0 20px ${activeEmotionData.themeColor}60, inset 0 0 15px ${activeEmotionData.themeColor}30`
                                    } : {}}
                                >
                                    <div className="card-img-wrapper">
                                        <img src={emotion.img} alt={emotion.name} />
                                    </div>
                                    <h2 style={isActive ? { color: activeEmotionData.themeColor, textShadow: `0 0 10px ${activeEmotionData.themeColor}80` } : {}}>{emotion.name}</h2>
                                    <p style={isActive ? { color: activeEmotionData.themeColor, opacity: 0.8 } : {}}>{emotion.sub}</p>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>

            {/* DEFAULT ACTION PROMPT (WHEN NOTHING IS CLICKED) */}
            {!selectedEmotion && !loading && !showResults && (
                <div className="action-prompt">
                    <div className="floating-icon">🎬</div>
                    <div className="prompt-text">SELECT A CHARACTER ABOVE TO BEGIN</div>
                </div>
            )}

            {/* LOADING STATE */}
            {loading && activeEmotionData && (
                <div className="loading-state">
                    <div className="cinebot-badge">✨ CINEBOT PICKS</div>
                    <div className={`loading-ring color-${activeEmotionData.color}`}>
                        <div className="loading-icon">🎬</div>
                    </div>
                    <div className="loading-dots">
                        <span className={`dot color-${activeEmotionData.color}`}></span>
                        <span className={`dot color-${activeEmotionData.color}`}></span>
                        <span className={`dot color-${activeEmotionData.color}`}></span>
                    </div>
                    <div className="loading-text">CINEBOT IS THINKING...</div>
                </div>
            )}

            {/* RESULTS STATE */}
            {showResults && activeEmotionData && (
                <div className="results-state">
                    <div className="cinebot-picks-divider">
                        <div className="divider-line"></div>
                        <div className="cinebot-badge results-badge" style={{ color: activeEmotionData.themeColor, borderColor: activeEmotionData.themeColor }}>
                            ★ CINEBOT PICKS
                        </div>
                        <div className="divider-line"></div>
                    </div>

                    <div className="quote-box" style={{ borderColor: activeEmotionData.themeColor }}>
                        <p>{activeEmotionData.quote}</p>
                    </div>

                    <div className="films-grid">
                        {activeEmotionData.movies.map((film, index) => (
                            <div className="film-card" key={film.id}>
                                <div className="film-cover">
                                    <div className="film-rank" style={{ backgroundColor: `${activeEmotionData.themeColor}30`, borderColor: activeEmotionData.themeColor }}>{index + 1}</div>
                                    <div className="film-year">{film.year}</div>
                                    <img src={film.img} alt={film.title} />
                                    <div className="film-overlay"></div>
                                </div>
                                <div className="film-details">
                                    <div className="film-meta">
                                        <span><span style={{ color: activeEmotionData.themeColor }}>★</span> {film.rating} IMDb</span>
                                        <span>🕒 {film.duration}</span>
                                    </div>
                                    <h3 className="film-title">{film.title}</h3>
                                    <div className="film-genre" style={{ color: activeEmotionData.themeColor }}>{film.genre}</div>

                                    <div className="match-bar-container">
                                        <div className="match-label">
                                            <span>EMOTION MATCH</span>
                                            <span style={{ color: activeEmotionData.themeColor }}>{film.match}</span>
                                        </div>
                                        <div className="match-bar-bg">
                                            <div className="match-bar-fill" style={{ width: film.match, backgroundColor: activeEmotionData.themeColor }}></div>
                                        </div>
                                    </div>

                                    <div className="about-film-box">
                                        <div className="about-title">ⓘ ABOUT THE FILM</div>
                                        <p className="about-desc">{film.desc}</p>
                                    </div>

                                    <div className="reason-box" style={{ backgroundColor: `${activeEmotionData.themeColor}10`, borderColor: `${activeEmotionData.themeColor}30` }}>
                                        <span className="reason-icon" style={{ color: activeEmotionData.themeColor }}>★</span>
                                        <p className="reason-text"><i>{film.reason}</i></p>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="reset-container">
                        <button
                            className="reset-button"
                            onClick={() => {
                                setSelectedEmotion(null);
                                setShowResults(false);
                            }}
                        >
                            <span className="reset-icon">↺</span> Try a different mood
                        </button>
                    </div>
                </div>
            )}

            {/* FOOTER CREDITS */}
            <div className="footer-credits">
                <a href="http://127.0.0.1:5500/Home_Page/index_home.html?page=1" className="back-to-home">← Back to Home</a>
                <span>Characters from Pixar's Inside Out · CineBot AI · Cineverse</span>
            </div>
        </div>
    );
}
