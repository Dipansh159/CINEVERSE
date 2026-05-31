import React, { useState, useEffect } from 'react';
import MoodMatcher from "./MoodMatcher";
import BattleMode from "./BattleMode";

function App() {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  useEffect(() => {
    const handleLocationChange = () => {
      setCurrentPath(window.location.pathname);
    };

    window.addEventListener('popstate', handleLocationChange);
    return () => window.removeEventListener('popstate', handleLocationChange);
  }, []);

  if (currentPath === '/battle') {
    return <BattleMode />;
  }

  return <MoodMatcher />;
}

export default App;