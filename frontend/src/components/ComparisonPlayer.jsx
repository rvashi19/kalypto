import React, { useState, useRef, useEffect } from 'react';

const ComparisonPlayer = ({ results }) => {
    const [currentMode, setCurrentMode] = useState('original'); // 'original', 'generic', 'cloned', 'emotion'
    const videoRef = useRef(null);
    const [isPlaying, setIsPlaying] = useState(false);

    // results is expected to be { original: url, generic: url, cloned: url, emotion: url }

    const handleModeChange = (mode) => {
        if (!results[mode]) return;

        const video = videoRef.current;
        const currentTime = video.currentTime;
        const wasPlaying = !video.paused;

        setCurrentMode(mode);

        // Use timeout to ensure React updates state and DOM before we manipulate video
        // Actually, with key prop or source update, we can handle it.
        // We will just update the src in the render, but we need to restore time after load.
    };

    // Use effect to restore time when source changes
    // This is tricky because loading takes time.
    // For MVP, we might just let it restart or use a more complex sync mechanism.
    // Let's try to sync.
    const [savedTime, setSavedTime] = useState(0);

    const onSrcChange = () => {
        const video = videoRef.current;
        if (video) {
            setSavedTime(video.currentTime);
            setIsPlaying(!video.paused);
        }
    };

    useEffect(() => {
        const video = videoRef.current;
        if (video && savedTime > 0) {
            video.currentTime = savedTime;
            if (isPlaying) video.play();
        }
    }, [currentMode]);

    const getLabel = (key) => {
        switch (key) {
            case 'original': return 'Original Voice';
            case 'generic': return 'Standard TTS';
            case 'cloned': return 'Basic Clone';
            case 'emotion': return 'Emotion-Preserving';
            default: return key;
        }
    };

    return (
        <div className="w-full max-w-4xl mx-auto space-y-6">
            <div className="relative aspect-video bg-black rounded-xl overflow-hidden shadow-2xl border border-slate-700">
                <video
                    ref={videoRef}
                    key={currentMode} // Force re-render on mode change if needed, but src change is enough usually. Key ensures clean slate.
                    // If we use key, we lose state completely. Let's try without key and just src change, OR use Key + savedTime restore.
                    // Using key ensures we don't display old frame.
                    src={results[currentMode]}
                    className="w-full h-full object-contain"
                    controls
                    onLoadedMetadata={(e) => {
                        if (savedTime > 0) e.target.currentTime = savedTime;
                        if (isPlaying) e.target.play();
                    }}
                />

                <div className="absolute top-4 left-4 bg-black/60 backdrop-blur-md px-3 py-1 rounded-full text-xs font-bold text-white uppercase tracking-wider border border-white/10">
                    {getLabel(currentMode)}
                </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {['original', 'generic', 'cloned', 'emotion'].map((mode) => (
                    <button
                        key={mode}
                        onClick={() => {
                            onSrcChange(); // Save state
                            handleModeChange(mode);
                        }}
                        disabled={!results[mode]}
                        className={`
                            relative px-4 py-3 rounded-xl font-medium text-sm transition-all duration-200
                            ${currentMode === mode
                                ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20 scale-105'
                                : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white hover:scale-105'
                            }
                            ${!results[mode] ? 'opacity-50 cursor-not-allowed hidden' : ''}
                        `}
                    >
                        {getLabel(mode)}
                        {currentMode === mode && (
                            <span className="absolute -bottom-2 left-1/2 transform -translate-x-1/2 w-1 h-1 bg-blue-400 rounded-full" />
                        )}
                    </button>
                ))}
            </div>
        </div>
    );
};

export default ComparisonPlayer;
