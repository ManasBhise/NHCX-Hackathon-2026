import React, { useState } from 'react';
import { UploadCloud, FileText, AlertCircle } from 'lucide-react';

export function UploadSection({ onUploadComplete, onChunk, onLog }) {
    const [isUploading, setIsUploading] = useState(false);
    const [file, setFile] = useState(null);
    const [progressText, setProgressText] = useState('');
    const [errorMessage, setErrorMessage] = useState('');
    const [progress, setProgress] = useState(0);

    const handleDragOver = (e) => {
        e.preventDefault();
    };

    const handleDrop = (e) => {
        e.preventDefault();
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            setFile(e.dataTransfer.files[0]);
            setErrorMessage('');
        }
    };

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setErrorMessage('');
        }
    };

    const handleStartExtraction = async () => {
        if (!file) return;
        setIsUploading(true);
        setErrorMessage('');
        setProgressText('Starting PDF extraction...');
        setProgress(0);

        const formData = new FormData();
        formData.append('file', file);

        // Start polling for progress
        const progressInterval = setInterval(async () => {
            try {
                const progressRes = await fetch('http://localhost:8000/progress');
                if (progressRes.ok) {
                    const progressData = await progressRes.json();
                    setProgress(progressData.current_step || 0);
                    setProgressText(progressData.message || 'Processing...');
                }
            } catch (err) {
                // Silently ignore progress polling errors
            }
        }, 500); // Poll every 500ms for smooth updates

        try {
            // Set a longer timeout for large PDFs (5 minutes)
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000);

            const response = await fetch('http://localhost:8000/convert', {
                method: 'POST',
                body: formData,
                signal: controller.signal,
            });

            clearInterval(progressInterval); // Stop polling when complete
            clearTimeout(timeoutId);

            if (!response.ok) {
                let errorMsg = `Server error ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.detail || errorMsg;
                } catch (e) {
                    // If response is not JSON, use status text
                    errorMsg = response.statusText || errorMsg;
                }
                throw new Error(errorMsg);
            }

            const data = await response.json();
            
            if (data.bundle) {
                setProgressText('✓ Conversion complete!');
                setProgress(100);
                
                // Call the callback with the full response
                onUploadComplete(data.bundle);
                
                // Log the success
                if (onLog) {
                    onLog('PDF successfully converted to FHIR Bundle');
                }
            } else {
                throw new Error('No bundle in response - backend did not return expected data');
            }

        } catch (err) {
            clearInterval(progressInterval); // Stop polling on error
            console.error('Extraction error', err);
            let errorMsg = err.message || 'Unknown error during extraction';
            
            // Handle specific error types
            if (err.name === 'AbortError') {
                errorMsg = 'Request timeout - PDF processing took too long (>5 minutes)';
            } else if (err instanceof TypeError && err.message === 'Failed to fetch') {
                errorMsg = 'Cannot reach backend server. Ensure backend is running on http://localhost:8000';
            }
            
            setErrorMessage(errorMsg);
            setProgressText(`❌ Error: ${errorMsg}`);
            if (onLog) {
                onLog(`Error: ${errorMsg}`);
            }
        } finally {
            setIsUploading(false);
            clearInterval(progressInterval);
        }
    };

    return (
        <div className="flex flex-col h-full animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="mb-6">
                <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Upload Insurance Plan</h2>
                <p className="text-gray-500 mt-1">Upload the PDF document to begin the extraction process.</p>
            </div>

            <div
                className="flex-1 border-2 border-dashed border-gray-300 rounded-xl bg-gray-50 flex flex-col items-center justify-center p-12 transition-colors hover:bg-gray-100 hover:border-gray-400"
                onDragOver={handleDragOver}
                onDrop={handleDrop}
            >
                {!isUploading && !file && (
                    <>
                        <UploadCloud className="w-16 h-16 text-gray-400 mb-4" />
                        <p className="text-gray-600 font-medium mb-2">Drop your PDF here, or click to select</p>
                        <p className="text-gray-500 text-sm mb-6">Supported format: PDF documents</p>
                        <label className="bg-white border border-gray-300 rounded-lg px-6 py-2 text-gray-700 font-medium cursor-pointer hover:bg-gray-50 transition-colors">
                            Choose File
                            <input
                                type="file"
                                accept=".pdf"
                                onChange={handleFileChange}
                                className="hidden"
                            />
                        </label>
                    </>
                )}

                {file && !isUploading && !errorMessage && (
                    <>
                        <FileText className="w-16 h-16 text-medical-400 mb-4" />
                        <p className="text-gray-900 font-medium mb-2">{file.name}</p>
                        <p className="text-gray-500 text-sm mb-6">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                        <button
                            onClick={handleStartExtraction}
                            className="bg-medical-600 hover:bg-medical-700 text-white font-medium py-3 px-8 rounded-lg shadow-sm transition-all"
                        >
                            Start Extraction
                        </button>
                        <button
                            onClick={() => {
                                setFile(null);
                                setErrorMessage('');
                            }}
                            className="text-gray-500 hover:text-gray-700 text-sm mt-4"
                        >
                            Change file
                        </button>
                    </>
                )}

                {isUploading && (
                    <>
                        <div className="w-12 h-12 border-4 border-medical-200 border-t-medical-600 rounded-full animate-spin mb-6"></div>
                        <p className="text-gray-900 font-medium mb-4">Processing PDF...</p>
                        <div className="w-full max-w-sm">
                            <div className="bg-gray-200 rounded-full h-2 overflow-hidden">
                                <div 
                                    className="bg-medical-600 h-full transition-all duration-300" 
                                    style={{ width: `${progress}%` }}
                                ></div>
                            </div>
                            <p className="text-gray-500 text-sm mt-2 text-center">{progress}%</p>
                        </div>
                        {progressText && (
                            <p className="text-gray-600 text-center mt-4 text-sm">{progressText}</p>
                        )}
                    </>
                )}

                {errorMessage && (
                    <div className="flex flex-col items-center text-center">
                        <AlertCircle className="w-16 h-16 text-red-400 mb-4" />
                        <p className="text-red-700 font-medium mb-2">Extraction Failed</p>
                        <p className="text-red-600 text-sm max-w-sm mb-6">{errorMessage}</p>
                        <button
                            onClick={() => {
                                setFile(null);
                                setErrorMessage('');
                                setProgressText('');
                            }}
                            className="bg-white border border-red-300 text-red-700 font-medium py-2 px-6 rounded-lg hover:bg-red-50 transition-colors"
                        >
                            Try Again
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
