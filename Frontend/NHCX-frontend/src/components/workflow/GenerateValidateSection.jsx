import React, { useState } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Activity } from 'lucide-react';

export function GenerateValidateSection({ reviewedData, onValidationComplete }) {
    const [status, setStatus] = useState('idle');
    const [validationData, setValidationData] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    const handleValidate = async () => {
        if (!reviewedData) {
            alert('No data to validate');
            return;
        }

        setIsLoading(true);
        setStatus('validating');

        try {
            // Create a JSON file from the reviewed data
            const jsonBlob = new Blob([JSON.stringify(reviewedData, null, 2)], {
                type: 'application/json'
            });

            const formData = new FormData();
            formData.append('file', jsonBlob, 'bundle.json');

            const response = await fetch('http://localhost:8000/validate', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Validation failed: ${response.status}`);
            }

            const result = await response.json();
            setValidationData(result);
            setStatus('completed');

            // DO NOT call onValidationComplete here - let user click Next button instead

        } catch (err) {
            console.error('Validation error', err);
            setStatus('completed');
            setValidationData({
                error: err.message,
                errors: [],
                warnings: []
            });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="mb-6">
                <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Validate Bundle</h2>
                <p className="text-gray-500 mt-1">Run FHIR and NHCX profile validation on your bundle.</p>
            </div>

            <div className="flex-1 overflow-y-auto">
                {status === 'idle' && !isLoading && (
                    <div className="bg-white border border-gray-200 rounded-xl p-12 flex flex-col items-center justify-center text-center shadow-sm h-64 mt-4">
                        <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mb-4">
                            <CheckCircle className="w-8 h-8 text-blue-500" />
                        </div>
                        <h3 className="text-lg font-medium text-gray-900 mb-2">Ready to Validate</h3>
                        <p className="text-gray-500 text-sm max-w-sm mb-6">
                            The payload has been reviewed. Run validation to check FHIR R4 and NHCX profile compliance.
                        </p>
                        <button
                            onClick={handleValidate}
                            disabled={isLoading}
                            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium py-3 px-8 rounded-lg shadow-sm transition-all"
                        >
                            Start Validation
                        </button>
                    </div>
                )}

                {(status === 'validating' || isLoading) && (
                    <div className="bg-white border border-gray-200 rounded-xl p-12 flex flex-col items-center justify-center text-center shadow-sm h-64 mt-4">
                        <div className="w-16 h-16 relative flex items-center justify-center mb-6">
                            <Activity className="w-8 h-8 text-blue-600 animate-pulse" />
                            <div className="absolute inset-0 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
                        </div>
                        <h3 className="text-lg font-medium text-gray-900 mb-2">Running Validation...</h3>
                        <p className="text-gray-500 text-sm max-w-sm">
                            Checking constraints against FHIR R4 and NHCX implementation guides.
                        </p>
                    </div>
                )}

                {status === 'completed' && validationData && (
                    <div className="space-y-6">
                        {/* Summary Card */}
                        <div className={`rounded-xl p-8 flex flex-col items-center text-center shadow-sm ${
                            validationData.error 
                                ? 'bg-red-50 border border-red-200'
                                : 'bg-white border border-gray-200'
                        }`}>
                            <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-4 ${
                                validationData.error
                                    ? 'bg-red-100 text-red-600'
                                    : 'bg-green-100 text-green-600'
                            }`}>
                                {validationData.error ? (
                                    <XCircle className="w-8 h-8" />
                                ) : (
                                    <CheckCircle className="w-8 h-8" />
                                )}
                            </div>
                            
                            {validationData.error ? (
                                <>
                                    <h3 className="text-xl font-bold text-red-900 mb-2">Validation Failed</h3>
                                    <p className="text-red-700 mb-4">{validationData.error}</p>
                                </>
                            ) : (
                                <>
                                    <h3 className="text-xl font-bold text-gray-900 mb-2">Validation Report</h3>
                                    <p className="text-gray-600 mb-6">Bundle analysis complete</p>

                                    {/* Validation Metrics */}
                                    <div className="grid grid-cols-3 gap-4 w-full max-w-md text-center">
                                        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                            <div className="text-3xl font-bold text-blue-600">
                                                {validationData.valid_percentage ?? validationData.completion_percentage ?? 0}%
                                            </div>
                                            <div className="text-xs text-gray-500 uppercase tracking-wider font-semibold mt-2">Valid</div>
                                        </div>
                                        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                            <div className="text-3xl font-bold text-amber-600">
                                                {validationData.compliance_percentage ?? 0}%
                                            </div>
                                            <div className="text-xs text-gray-500 uppercase tracking-wider font-semibold mt-2">Compliant</div>
                                        </div>
                                        <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                            <div className="text-3xl font-bold text-gray-700">
                                                {validationData.passed_checks ?? 0}/{validationData.total_checks ?? 0}
                                            </div>
                                            <div className="text-xs text-gray-500 uppercase tracking-wider font-semibold mt-2">Checks</div>
                                        </div>
                                    </div>
                                </>
                            )}
                        </div>

                        {/* Error Count Summary */}
                        {!validationData.error && (
                            <div className="grid grid-cols-2 gap-4">
                                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                                    <div className="text-2xl font-bold text-red-600">{validationData.error_count || 0}</div>
                                    <div className="text-sm text-red-700 font-medium">Errors</div>
                                </div>
                                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                                    <div className="text-2xl font-bold text-amber-600">{validationData.warning_count || 0}</div>
                                    <div className="text-sm text-amber-700 font-medium">Warnings</div>
                                </div>
                            </div>
                        )}

                        {/* Errors List */}
                        {validationData.errors && validationData.errors.length > 0 && (
                            <div className="bg-white border border-red-200 rounded-xl overflow-hidden shadow-sm">
                                <div className="bg-red-50 px-4 py-3 border-b border-red-100 flex items-center gap-2">
                                    <AlertTriangle className="w-5 h-5 text-red-500" />
                                    <span className="font-semibold text-red-800">Errors ({validationData.errors.length})</span>
                                </div>
                                <ul className="divide-y divide-gray-100">
                                    {validationData.errors.map((err, i) => (
                                        <li key={i} className="p-4 hover:bg-gray-50">
                                            <div className="flex gap-3 mb-2">
                                                <XCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                                                <div className="flex-1">
                                                    <p className="font-semibold text-gray-900">
                                                        {err.resource} → {err.field}
                                                    </p>
                                                    <p className="text-sm text-gray-600 mt-1">{err.message}</p>
                                                    {err.remediation && (
                                                        <p className="text-sm text-blue-600 mt-2 bg-blue-50 p-2 rounded">
                                                            💡 {err.remediation}
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {/* Warnings List */}
                        {validationData.warnings && validationData.warnings.length > 0 && (
                            <div className="bg-white border border-amber-200 rounded-xl overflow-hidden shadow-sm">
                                <div className="bg-amber-50 px-4 py-3 border-b border-amber-100 flex items-center gap-2">
                                    <AlertTriangle className="w-5 h-5 text-amber-500" />
                                    <span className="font-semibold text-amber-800">Warnings ({validationData.warnings.length})</span>
                                </div>
                                <ul className="divide-y divide-gray-100">
                                    {validationData.warnings.map((warn, i) => (
                                        <li key={i} className="p-4 hover:bg-gray-50">
                                            <div className="flex gap-3 mb-2">
                                                <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                                                <div className="flex-1">
                                                    <p className="font-semibold text-gray-900">
                                                        {warn.resource} → {warn.field}
                                                    </p>
                                                    <p className="text-sm text-gray-600 mt-1">{warn.message}</p>
                                                    {warn.remediation && (
                                                        <p className="text-sm text-blue-600 mt-2 bg-blue-50 p-2 rounded">
                                                            💡 {warn.remediation}
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {/* Detailed Report - Hidden for now */}
                        {/* validationData.detailed_report && (
                            <div className="bg-gray-900 rounded-xl p-4 overflow-x-auto">
                                <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap break-words">
                                    {validationData.detailed_report}
                                </pre>
                            </div>
                        ) */}

                        {/* Action Button */}
                        {!validationData.error && (
                            <div className="flex gap-3 justify-center">
                                <button
                                    onClick={() => {
                                        // Proceed to download/next step
                                        onValidationComplete({
                                            ...validationData,
                                            fhirJson: reviewedData
                                        });
                                    }}
                                    className="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-6 rounded-lg shadow-sm transition-all"
                                >
                                    Next
                                </button>
                                <button
                                    onClick={() => {
                                        setStatus('idle');
                                        setValidationData(null);
                                    }}
                                    className="bg-gray-600 hover:bg-gray-700 text-white font-medium py-2 px-6 rounded-lg shadow-sm transition-all"
                                >
                                    Run Again
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

