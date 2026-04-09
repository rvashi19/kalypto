import React, { useEffect, useRef, useState } from 'react';

const formatPercent = (value) => {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        return 'N/A';
    }
    return `${(value * 100).toFixed(1)}%`;
};

const formatNumber = (value, digits = 2) => {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        return 'N/A';
    }
    return value.toFixed(digits);
};

const ComparisonPlayer = ({ results }) => {
    const videoRef = useRef(null);
    const [currentMode, setCurrentMode] = useState(results.dubbed ? 'dubbed' : 'original');
    const [savedTime, setSavedTime] = useState(0);
    const [resumePlayback, setResumePlayback] = useState(false);

    const modes = [
        results.original ? { key: 'original', label: 'Original video' } : null,
        results.dubbed ? { key: 'dubbed', label: `Dubbed ${results.target_language || ''}`.trim() } : null,
    ].filter(Boolean);

    useEffect(() => {
        setCurrentMode(results.dubbed ? 'dubbed' : 'original');
    }, [results.dubbed, results.original]);

    const switchMode = (mode) => {
        const video = videoRef.current;
        if (video) {
            setSavedTime(video.currentTime);
            setResumePlayback(!video.paused);
        }
        setCurrentMode(mode);
    };

    const currentSrc = currentMode === 'dubbed' ? results.dubbed : results.original;
    const metrics = results.metrics || {};
    const alignedMetrics = metrics.aligned_metrics || {};
    const rawMetrics = metrics.raw_metrics || {};
    const artifacts = results.artifacts || {};

    const downloadItems = [
        { label: 'Dubbed video', href: results.dubbed },
        { label: 'Dubbed audio', href: results.dubbed_audio },
        { label: 'Run summary', href: results.run_summary_url },
        { label: 'Metrics JSON', href: results.metrics_url },
        { label: 'Segment manifest', href: results.manifest_url },
        { label: 'Transcription', href: results.transcription_url },
        { label: 'Translation', href: results.translation_url },
    ].filter((item) => item.href);

    return (
        <div className="w-full max-w-6xl mx-auto grid gap-8 xl:grid-cols-[1.3fr,0.9fr]">
            <div className="space-y-6">
                <div className="relative aspect-video bg-black rounded-3xl overflow-hidden shadow-2xl border border-slate-700">
                    {currentSrc ? (
                        <video
                            ref={videoRef}
                            key={currentMode}
                            src={currentSrc}
                            className="w-full h-full object-contain"
                            controls
                            onLoadedMetadata={(event) => {
                                if (savedTime > 0) {
                                    event.target.currentTime = savedTime;
                                }
                                if (resumePlayback) {
                                    event.target.play().catch(() => null);
                                }
                            }}
                        />
                    ) : (
                        <div className="w-full h-full flex items-center justify-center text-slate-400">
                            No playable video output was generated.
                        </div>
                    )}

                    <div className="absolute top-4 left-4 bg-black/70 backdrop-blur-md px-3 py-1 rounded-full text-xs font-bold text-white uppercase tracking-wider border border-white/10">
                        {currentMode === 'dubbed' ? `Dubbed ${results.target_language || ''}`.trim() : 'Original'}
                    </div>
                </div>

                <div className="flex flex-wrap gap-3">
                    {modes.map((mode) => (
                        <button
                            key={mode.key}
                            type="button"
                            onClick={() => switchMode(mode.key)}
                            className={`px-4 py-3 rounded-2xl text-sm font-medium transition-all duration-200 ${currentMode === mode.key
                                ? 'bg-blue-600 text-white shadow-lg shadow-blue-950/40'
                                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                                }`}
                        >
                            {mode.label}
                        </button>
                    ))}
                </div>

                {results.plot_url && (
                    <div className="rounded-3xl border border-slate-700 bg-slate-900/80 p-5 space-y-4">
                        <div>
                            <p className="text-xs uppercase tracking-[0.3em] text-slate-500 mb-2">Prosody Match</p>
                            <h3 className="text-xl font-semibold text-white">Aligned pitch and energy overlay</h3>
                        </div>
                        <div className="bg-white rounded-2xl overflow-hidden">
                            <img src={results.plot_url} alt="Prosody comparison plot" className="w-full h-auto object-cover" />
                        </div>
                    </div>
                )}
            </div>

            <div className="space-y-6">
                <div className="rounded-3xl border border-slate-700 bg-slate-900/80 p-6 space-y-5">
                    <div>
                        <p className="text-xs uppercase tracking-[0.3em] text-slate-500 mb-2">Run Overview</p>
                        <h3 className="text-xl font-semibold text-white">Emotion-preserving dub summary</h3>
                    </div>

                    <div className="grid sm:grid-cols-2 gap-4">
                        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                            <p className="text-sm text-slate-400">Target language</p>
                            <p className="text-lg font-semibold text-white mt-1">{results.target_language || 'N/A'}</p>
                        </div>
                        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                            <p className="text-sm text-slate-400">Run validity</p>
                            <p className="text-lg font-semibold text-white mt-1">{results.run_validity || 'N/A'}</p>
                        </div>
                        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                            <p className="text-sm text-slate-400">Valence</p>
                            <p className="text-lg font-semibold text-white mt-1">{formatNumber(metrics.valence, 3)}</p>
                        </div>
                        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                            <p className="text-sm text-slate-400">Arousal</p>
                            <p className="text-lg font-semibold text-white mt-1">{formatNumber(metrics.arousal, 3)}</p>
                        </div>
                        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                            <p className="text-sm text-slate-400">Source profile</p>
                            <p className="text-sm font-semibold text-white mt-1">{results.source_type || 'N/A'}</p>
                        </div>
                        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                            <p className="text-sm text-slate-400">Segments processed</p>
                            <p className="text-lg font-semibold text-white mt-1">{metrics.segment_count ?? 'N/A'}</p>
                        </div>
                    </div>
                </div>

                {(results.transcription_text || results.translation_text) && (
                    <div className="rounded-3xl border border-slate-700 bg-slate-900/80 p-6 space-y-5">
                        <div>
                            <p className="text-xs uppercase tracking-[0.3em] text-slate-500 mb-2">Dialogue Flow</p>
                            <h3 className="text-xl font-semibold text-white">Source speech to dubbed text</h3>
                        </div>

                        {results.transcription_text && (
                            <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                                <p className="text-sm text-slate-400 mb-2">Transcribed source</p>
                                <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{results.transcription_text}</p>
                            </div>
                        )}

                        {results.translation_text && (
                            <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                                <p className="text-sm text-slate-400 mb-2">Dub translation</p>
                                <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{results.translation_text}</p>
                            </div>
                        )}
                    </div>
                )}

                <div className="rounded-3xl border border-slate-700 bg-slate-900/80 p-6 space-y-5">
                    <div>
                        <p className="text-xs uppercase tracking-[0.3em] text-slate-500 mb-2">MIR Metrics</p>
                        <h3 className="text-xl font-semibold text-white">Aligned evaluation</h3>
                    </div>

                    <div className="grid gap-4">
                        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                            <p className="text-sm text-slate-400">Pitch correlation</p>
                            <p className="text-2xl font-semibold text-blue-400 mt-1">{formatPercent(alignedMetrics.pitch_correlation)}</p>
                            <p className="text-xs text-slate-500 mt-2">Raw: {formatPercent(rawMetrics.pitch_correlation)}</p>
                        </div>

                        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                            <p className="text-sm text-slate-400">Energy correlation</p>
                            <p className="text-2xl font-semibold text-emerald-400 mt-1">{formatPercent(alignedMetrics.energy_correlation)}</p>
                            <p className="text-xs text-slate-500 mt-2">Raw: {formatPercent(rawMetrics.energy_correlation)}</p>
                        </div>

                        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                            <p className="text-sm text-slate-400">Mel-cepstral distortion</p>
                            <p className="text-2xl font-semibold text-amber-300 mt-1">{formatNumber(alignedMetrics.mcd_score, 2)}</p>
                            <p className="text-xs text-slate-500 mt-2">Raw: {formatNumber(rawMetrics.mcd_score, 2)}</p>
                        </div>
                    </div>
                </div>

                <div className="rounded-3xl border border-slate-700 bg-slate-900/80 p-6 space-y-4">
                    <div>
                        <p className="text-xs uppercase tracking-[0.3em] text-slate-500 mb-2">Artifacts</p>
                        <h3 className="text-xl font-semibold text-white">Download outputs</h3>
                    </div>

                    <div className="flex flex-wrap gap-3">
                        {downloadItems.map((item) => (
                            <a
                                key={item.label}
                                href={item.href}
                                target="_blank"
                                rel="noreferrer"
                                className="px-4 py-2 rounded-xl bg-slate-800 text-slate-200 hover:bg-slate-700 transition-colors text-sm"
                            >
                                {item.label}
                            </a>
                        ))}
                    </div>

                    {results.summary && (
                        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
                            {results.summary}
                        </div>
                    )}

                    {artifacts.source_audio && !results.dubbed && (
                        <p className="text-sm text-slate-400">
                            The pipeline produced aligned audio artifacts, but no remuxed video was generated for this run.
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ComparisonPlayer;
