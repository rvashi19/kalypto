import React, { useRef, useState } from 'react';

const LANGUAGE_OPTIONS = [
    'English',
    'Spanish',
    'French',
    'German',
    'Hindi',
    'Gujarati',
    'Italian',
    'Portuguese',
    'Japanese',
];

const SUPPORTED_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v'];

const UploadArea = ({ onUpload, onUseDemo, onLanguageChange, selectedLanguage, isUploading }) => {
    const [dragActive, setDragActive] = useState(false);
    const inputRef = useRef(null);

    const handleDrag = (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (event.type === 'dragenter' || event.type === 'dragover') {
            setDragActive(true);
        } else if (event.type === 'dragleave') {
            setDragActive(false);
        }
    };

    const handleDrop = (event) => {
        event.preventDefault();
        event.stopPropagation();
        setDragActive(false);
        if (event.dataTransfer.files && event.dataTransfer.files[0]) {
            handleFile(event.dataTransfer.files[0]);
        }
    };

    const handleChange = (event) => {
        event.preventDefault();
        if (event.target.files && event.target.files[0]) {
            handleFile(event.target.files[0]);
        }
    };

    const handleFile = (file) => {
        const normalizedName = file.name?.toLowerCase() || '';
        const looksLikeVideo = file.type.startsWith('video/')
            || SUPPORTED_VIDEO_EXTENSIONS.some((extension) => normalizedName.endsWith(extension));

        if (looksLikeVideo) {
            onUpload(file);
        } else {
            alert('Please upload a video file such as MP4, MOV, WEBM, MKV, or AVI.');
        }
    };

    return (
        <div className="w-full max-w-3xl mx-auto grid gap-6 lg:grid-cols-[1.35fr,0.9fr]">
            <div
                className={`p-8 rounded-3xl border-2 border-dashed transition-all duration-300 ${dragActive
                    ? 'border-blue-500 bg-blue-500/10'
                    : 'border-slate-700 bg-slate-800/80 hover:border-blue-400'
                    }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
            >
                <input
                    ref={inputRef}
                    type="file"
                    className="hidden"
                    onChange={handleChange}
                    accept="video/*"
                    disabled={isUploading}
                />

                <div className="flex flex-col items-center justify-center space-y-4 text-center min-h-[280px]">
                    <div className={`p-4 rounded-full ${dragActive ? 'bg-blue-500/20' : 'bg-slate-700'}`}>
                        <svg className="w-8 h-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                    </div>

                    <div className="space-y-2">
                        <h3 className="text-2xl font-semibold text-white">Upload a source video</h3>
                        <p className="text-slate-400 text-sm leading-relaxed max-w-md">
                            Drop an MP4, MOV, or WEBM clip and the backend will extract speech, analyze acoustic emotion,
                            translate it into {selectedLanguage}, and render a remixed dubbed output.
                        </p>
                    </div>

                    <button
                        type="button"
                        onClick={() => inputRef.current?.click()}
                        disabled={isUploading}
                        className="px-5 py-3 rounded-xl bg-blue-500 hover:bg-blue-400 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Choose video
                    </button>

                    <button
                        type="button"
                        onClick={onUseDemo}
                        disabled={isUploading}
                        className="px-5 py-3 rounded-xl border border-slate-600 bg-slate-900 hover:bg-slate-800 text-slate-100 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Run built-in movie clip demo
                    </button>

                    <p className="text-xs text-slate-500">
                        Best results come from a 5 to 25 second single-speaker dialogue clip with a real audio track.
                    </p>
                </div>
            </div>

            <div className="rounded-3xl border border-slate-700 bg-slate-900/80 p-6 space-y-5">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-slate-500 mb-2">Dub Settings</p>
                    <h3 className="text-xl font-semibold text-white">Target language</h3>
                    <p className="text-sm text-slate-400 mt-1">
                        The backend will translate and synthesize speech for this language while preserving timing and emotion cues.
                    </p>
                </div>

                <label className="block space-y-2">
                    <span className="text-sm font-medium text-slate-300">Language</span>
                    <select
                        value={selectedLanguage}
                        onChange={(event) => onLanguageChange(event.target.value)}
                        className="w-full rounded-xl border border-slate-700 bg-slate-800 px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                        disabled={isUploading}
                    >
                        {LANGUAGE_OPTIONS.map((language) => (
                            <option key={language} value={language}>
                                {language}
                            </option>
                        ))}
                    </select>
                </label>

                <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 space-y-2">
                    <p className="text-sm font-medium text-white">Pipeline stages</p>
                    <p className="text-sm text-slate-400">Demux and normalize audio</p>
                    <p className="text-sm text-slate-400">Extract MIR fingerprint and valence/arousal</p>
                    <p className="text-sm text-slate-400">Translate, synthesize, stretch, align, and remux</p>
                </div>

                <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-2">
                    <p className="text-sm font-medium text-amber-100">Presentation demo</p>
                    <p className="text-sm text-amber-50/80">
                        The built-in demo uses your supplied movie clip and routes it through the same dubbing pipeline for a cleaner showcase.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default UploadArea;
