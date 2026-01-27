import React, { useState, useRef } from 'react';

const UploadArea = ({ onUpload }) => {
    const [dragActive, setDragActive] = useState(false);
    const inputRef = useRef(null);

    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFile(e.dataTransfer.files[0]);
        }
    };

    const handleChange = (e) => {
        e.preventDefault();
        if (e.target.files && e.target.files[0]) {
            handleFile(e.target.files[0]);
        }
    };

    const handleFile = (file) => {
        // Basic validation
        if (file.type.startsWith('video/')) {
            onUpload(file);
        } else {
            alert("Please upload a video file.");
        }
    };

    const onButtonClick = () => {
        inputRef.current.click();
    };

    return (
        <div
            className={`w-full max-w-xl mx-auto p-8 rounded-2xl border-2 border-dashed transition-all duration-300 ${dragActive
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-slate-600 bg-slate-800 hover:border-blue-400"
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
            />

            <div className="flex flex-col items-center justify-center space-y-4 text-center">
                <div className={`p-4 rounded-full ${dragActive ? 'bg-blue-500/20' : 'bg-slate-700'}`}>
                    <svg className="w-8 h-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                </div>

                <div>
                    <h3 className="text-xl font-semibold text-white mb-1">
                        Upload Video
                    </h3>
                    <p className="text-slate-400 text-sm">
                        Drag & drop a video or <button onClick={onButtonClick} className="text-blue-400 hover:text-blue-300 font-medium">click to browse</button>
                    </p>
                </div>

                <p className="text-xs text-slate-500">
                    Supports MP4, MOV, WEBM (Max 50MB)
                </p>
            </div>
        </div>
    );
};

export default UploadArea;
