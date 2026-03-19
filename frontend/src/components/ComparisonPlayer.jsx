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
<<<<<<< HEAD
            </div>
=======
        </div>

            {/* MIR Evaluation Section */}
            {results.metrics && (
                <div className="mt-8 bg-slate-800/50 rounded-2xl p-6 border border-slate-700/50 backdrop-blur-sm animate-fade-in-up">
                    <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                        <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                        Quantitative MIR Evaluation
                    </h3>
                    
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                        <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800">
                            <p className="text-sm text-slate-400 font-medium mb-1">MCD Score (Distortion)</p>
                            <p className="text-2xl font-bold text-white">{results.metrics.mcd_score.toFixed(2)}</p>
                            <p className="text-xs text-slate-500 mt-1">Lower is better (closer voiceprint)</p>
                        </div>
                        <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800">
                            <p className="text-sm text-slate-400 font-medium mb-1">Pitch Correlation</p>
                            <p className="text-2xl font-bold text-blue-400">{(results.metrics.pitch_correlation * 100).toFixed(1)}%</p>
                            <p className="text-xs text-slate-500 mt-1">DTW-aligned F0 contour match</p>
                        </div>
                        <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800">
                            <p className="text-sm text-slate-400 font-medium mb-1">Energy Correlation</p>
                            <p className="text-2xl font-bold text-violet-400">{(results.metrics.energy_correlation * 100).toFixed(1)}%</p>
                            <p className="text-xs text-slate-500 mt-1">RMS envelope rhythm match</p>
                        </div>
                    </div>

                    {results.plot_url && (
                        <div className="mt-6">
                            <p className="text-sm text-slate-400 font-medium mb-3">Prosody Alignment (Original vs. Dubbed)</p>
                            <div className="bg-white rounded-xl overflow-hidden shadow-inner border border-slate-700">
                                <img src={results.plot_url} alt="Prosody Match Plot" className="w-full h-auto object-cover" />
                            </div>
                        </div>
                    )}
                </div>
            )}
>>>>>>> c5552c8 (Initial Milestone: Modular refactor complete. Implements full pipeline intelligence decoupled from services.)
        </div>
    );
};

export default ComparisonPlayer;
