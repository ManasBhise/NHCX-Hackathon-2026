import React, { useState } from 'react';
import { TopNav } from './components/TopNav';
import { StepIndicator } from './components/StepIndicator';
import { JsonPanel } from './components/JsonPanel';
import { UploadSection } from './components/workflow/UploadSection';
import { ReviewSection } from './components/workflow/ReviewSection';
import { GenerateValidateSection } from './components/workflow/GenerateValidateSection';
import { DownloadSection } from './components/workflow/DownloadSection';

function App() {
    const [currentStep, setCurrentStep] = useState(0);
    const [highestStep, setHighestStep] = useState(0);

    // Centralized application state
    const [extractedContext, setExtractedContext] = useState(null);
    const [streamingText, setStreamingText] = useState('');
    const [processingLogs, setProcessingLogs] = useState([]);
    const [reviewedData, setReviewedData] = useState(null);
    const [validationResult, setValidationResult] = useState(null);

    const handleUploadComplete = (data) => {
        // data is the FHIR Bundle from /convert endpoint
        setStreamingText('');
        setProcessingLogs([]);
        setExtractedContext(data);
        setCurrentStep(1); // Go to Review step for editing
        setHighestStep(prev => Math.max(prev, 1));
    };

    const handleReviewComplete = (data) => {
        setReviewedData(data);
        setCurrentStep(2); // Move to Generate & Validate
        setHighestStep(prev => Math.max(prev, 2));
    };

    const handleValidationComplete = (result) => {
        setValidationResult(result);
        // Move to Download section regardless of validation errors/warnings
        // Users should be able to see/download even with issues
        if (!result.error) {
            setCurrentStep(3); // Move to Download
            setHighestStep(prev => Math.max(prev, 3));
        }
    };

    const handleReset = () => {
        setCurrentStep(0);
        setHighestStep(0);
        setExtractedContext(null);
        setStreamingText('');
        setProcessingLogs([]);
        setReviewedData(null);
        setValidationResult(null);
    };

    const handleStepClick = (stepId) => {
        if (stepId <= highestStep) {
            setCurrentStep(stepId);
        }
    };

    // Determine what data to show in JSON panel based on current step
    const getContextData = () => {
        // if we already have a final extracted context (after upload completes), show it
        if (extractedContext) {
            return {
                status: "Structured Review JSON",
                data: extractedContext
            };
        }
        // if upload is in progress and we have received streaming text, display it
        if (streamingText.length > 0) {
            // Try to show what we have so far, even if not complete JSON
            try {
                const parsed = JSON.parse(streamingText);
                return {
                    status: "Streaming JSON (in progress)",
                    data: parsed
                };
            } catch (e) {
                // If not valid JSON yet, show as raw text
                return {
                    status: "Streaming data from server...",
                    data: { raw_streaming_text: streamingText }
                };
            }
        }
        // if no streaming text but we do have progress logs, show them
        if (processingLogs.length > 0) {
            return {
                status: "Processing",
                data: { logs: processingLogs }
            };
        }
        return { status: "Awaiting PDF file..." };
    };

    const handleReviewDataChange = (updatedData) => {
        setExtractedContext(prev => ({
            ...prev,
            extractedData: updatedData
        }));
    };

    return (
        <div className="h-screen w-screen flex flex-col bg-gray-50 overflow-hidden font-sans">
            <TopNav />
            <StepIndicator
                currentStep={currentStep}
                highestStep={highestStep}
                onStepClick={handleStepClick}
            />

            <main className="flex-1 flex overflow-hidden">
                {/* Left Workflow Area */}
                <div className="flex-[3] overflow-y-auto p-4 md:p-8 custom-scrollbar">
                    <div className="h-full flex flex-col max-w-5xl mx-auto">
                        {currentStep === 0 && <UploadSection onUploadComplete={handleUploadComplete} onChunk={(chunk) => setStreamingText(prev => prev + chunk)} onLog={(msg) => setProcessingLogs(prev => [...prev, msg])} />}
                        {currentStep === 1 && <ReviewSection
                            data={extractedContext}
                            onReviewComplete={handleReviewComplete}
                            onDataChange={handleReviewDataChange}
                        />}
                        {currentStep === 2 && <GenerateValidateSection reviewedData={extractedContext || reviewedData} onValidationComplete={handleValidationComplete} />}
                        {currentStep === 3 && <DownloadSection fhirBundle={validationResult} bundleToDownload={validationResult?.fhirJson || getContextData().data} onReset={handleReset} />}
                    </div>
                </div>

                {/* Right JSON Panel */}
                <div className="flex-[3] hidden lg:block border-l border-[#333]"> 
                    <JsonPanel
                        step={currentStep}
                        data={getContextData()}
                        onJsonEdit={(parsedData) => {
                            // Expecting the same structure used throughout: { status: "..", data: { extractedData: {...} } }
                            if (parsedData?.data) {
                                setExtractedContext(parsedData.data);
                                // Once user saves JSON, move them to the Review step
                                setCurrentStep(1);
                                setHighestStep(prev => Math.max(prev, 1));
                            }
                        }}
                    />
                </div>
            </main>
        </div>
    );
}

export default App;
