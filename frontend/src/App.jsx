import React, { useState, useEffect } from 'react';
import UploadArea from './components/UploadArea';
import ComparisonPlayer from './components/ComparisonPlayer';
import { uploadVideo, getJobStatus, startDemoJob } from './services/api';

function App() {
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null); // 'queued', 'processing', 'completed', 'failed'
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [targetLanguage, setTargetLanguage] = useState('English');

  const handleUpload = async (file) => {
    try {
      setError(null);
      setResults(null);
      const data = await uploadVideo(file, targetLanguage);
      setJobId(data.job_id);
      setStatus(data.status);
      setMessage(data.message || `Queued ${targetLanguage} dubbing job...`);
    } catch (err) {
      console.error(err);
      setError("Upload failed. Please try again.");
    }
  };

  const handleDemo = async () => {
    try {
      setError(null);
      setResults(null);
      const data = await startDemoJob(targetLanguage);
      setJobId(data.job_id);
      setStatus(data.status);
      setMessage(data.message || `Queued demo job for ${targetLanguage}...`);
    } catch (err) {
      console.error(err);
      setError("Demo launch failed. Please try again.");
    }
  };

  useEffect(() => {
    let interval;
    if (jobId && status !== 'completed' && status !== 'failed') {
      interval = setInterval(async () => {
        try {
          const data = await getJobStatus(jobId);
          setStatus(data.status);
          setProgress(data.progress || 0);
          setMessage(data.message || '');
          if (data.status === 'completed') {
            setResults(data.results);
            clearInterval(interval);
          } else if (data.status === 'failed') {
            setError(data.message || "Processing failed");
            clearInterval(interval);
          }
        } catch (err) {
          console.error("Polling error", err);
        }
      }, 2000); // Poll every 2 seconds
    }
    return () => clearInterval(interval);
  }, [jobId, status]);

  const reset = () => {
    setJobId(null);
    setStatus(null);
    setResults(null);
    setError(null);
    setProgress(0);
    setMessage('');
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 font-sans selection:bg-blue-500/30">

      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-violet-600 rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/20">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            </div>
            <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
              TrueDub <span className="text-xs font-normal text-slate-500 ml-1 border border-slate-700 px-1.5 py-0.5 rounded-md">BETA</span>
            </h1>
          </div>

          <button
            onClick={reset}
            className="text-sm font-medium text-slate-400 hover:text-white transition-colors"
          >
            New Project
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-12 flex flex-col items-center justify-center min-h-[80vh]">

        {/* Hero Text */}
        {!jobId && !results && (
          <div className="text-center mb-12 space-y-4 max-w-2xl">
            <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight text-white">
              Dub videos with <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-violet-400">emotional intelligence</span>
            </h2>
            <p className="text-lg text-slate-400 leading-relaxed">
              Upload a clip, choose a target language, and generate a localhost dub that preserves timing, energy, and emotional delivery through MIR-guided analysis.
            </p>
          </div>
        )}

        {/* Upload State */}
        {!jobId && (
          <div className="w-full transition-all duration-500 transform translate-y-0 opacity-100">
            <UploadArea
              onUpload={handleUpload}
              onUseDemo={handleDemo}
              onLanguageChange={setTargetLanguage}
              selectedLanguage={targetLanguage}
              isUploading={status === 'queued' || status === 'processing'}
            />
            {error && (
              <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-center max-w-xl mx-auto">
                {error}
              </div>
            )}
          </div>
        )}

        {/* Processing State */}
        {jobId && !results && !error && (
          <div className="w-full max-w-xl space-y-8 animate-fade-in">
            <div className="relative pt-1">
              <div className="flex mb-2 items-center justify-between">
                <div>
                  <span className="text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full text-blue-600 bg-blue-200">
                    {status || 'Processing'}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-xs font-semibold inline-block text-blue-600">
                    {Math.round(progress)}%
                  </span>
                </div>
              </div>
              <div className="overflow-hidden h-2 mb-4 text-xs flex rounded bg-slate-800">
                <div style={{ width: `${progress}%` }} className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-blue-500 transition-all duration-500"></div>
              </div>
              <p className="text-center text-xs uppercase tracking-[0.3em] text-slate-500 mb-3">
                Target language: {targetLanguage}
              </p>
              <p className="text-center text-slate-400 animate-pulse">{message || 'Initializing magic...'}</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && jobId && (
          <div className="text-center space-y-4">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 text-red-500 mb-4">
              <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-xl font-bold text-white">Something went wrong</h3>
            <p className="text-slate-400 max-w-md">{error}</p>
            <div className="flex flex-wrap justify-center gap-3">
              <button
                onClick={reset}
                className="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors"
              >
                Try Again
              </button>
              <button
                onClick={async () => {
                  reset();
                  await handleDemo();
                }}
                className="px-6 py-2 bg-blue-500 hover:bg-blue-400 text-white rounded-lg transition-colors"
              >
                Run Built-in Demo
              </button>
            </div>
          </div>
        )}

        {/* Results State */}
        {results && (
          <div className="w-full animate-fade-in-up">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-white mb-2">Dubbing Complete</h2>
              <p className="text-slate-400">
                Review the original video, the {results.target_language || targetLanguage} dub, and the underlying MIR validation outputs.
              </p>
            </div>
            <ComparisonPlayer results={results} />
          </div>
        )}

      </main>
    </div>
  )
}

export default App
