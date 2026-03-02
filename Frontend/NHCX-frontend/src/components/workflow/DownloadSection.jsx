import React, { useState } from 'react';
import { FileJson, FileSpreadsheet, Copy, Check, DownloadCloud, RefreshCw } from 'lucide-react';

export function DownloadSection({ fhirBundle, onReset, bundleToDownload }) {
    const [copied, setCopied] = useState(false);

    // Determine source JSON for download / display. Prefer the explicit
    // `bundleToDownload` (which mirrors the Console & JSON Context). Fall
    // back to `fhirBundle.fhirJson` (legacy behavior).
    const resolvedBundle = bundleToDownload || (fhirBundle && (fhirBundle.bundle || fhirBundle.fhirJson || fhirBundle));
    const jsonString = resolvedBundle ? JSON.stringify(resolvedBundle, null, 2) : "{}";

    const handleCopy = () => {
        navigator.clipboard.writeText(jsonString);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleDownload = () => {
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `nhcx-bundle-${new Date().getTime()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const handleDownloadExcel = async () => {
        try {
            // Create FormData with the JSON as a file
            const formData = new FormData();
            const jsonBlob = new Blob([jsonString], { type: 'application/json' });
            formData.append('file', jsonBlob, 'bundle.json');

            const resp = await fetch('http://localhost:8000/json-to-excel', {
                method: 'POST',
                body: formData
            });
            if (!resp.ok) {
                let details = '';
                try {
                    const json = await resp.json();
                    if (json && json.detail) details = json.detail;
                } catch {}
                throw new Error(`Server ${resp.status} ${details}`);
            }
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `nhcx-mapping-${new Date().getTime()}.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (err) {
            console.error('Excel download failed', err);
            alert(err.message || 'Excel download failed');
        }
    };


    return (
        <div className="flex flex-col h-full animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="mb-6 flex justify-between items-end">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Export Artifact</h2>
                    <p className="text-gray-500 mt-1">Download the generated JSON or export to Excel.</p>
                </div>
                <button
                    onClick={onReset}
                    className="text-gray-500 hover:text-medical-600 flex items-center gap-1.5 text-sm font-medium transition-colors bg-white border border-gray-200 px-3 py-1.5 rounded-md hover:bg-gray-50 shadow-sm"
                >
                    <RefreshCw className="w-4 h-4" /> Start New
                </button>
            </div>

            <div className="flex-1 bg-[#1E1E1E] rounded-xl border border-gray-800 shadow-lg overflow-hidden flex flex-col">
                <div className="bg-[#252526] px-4 py-3 flex justify-between items-center border-b border-[#333]">
                    <div className="flex items-center gap-2 text-gray-300">
                        <FileJson className="w-5 h-5 text-medical-400" />
                        <span className="text-sm font-medium font-mono">bundle-output.json</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleCopy}
                            className="p-1.5 text-gray-400 hover:text-white hover:bg-[#333] rounded transition-colors"
                            title="Copy to clipboard"
                        >
                            {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                        </button>
                    </div>
                </div>
                <div className="flex-1 overflow-auto p-4 custom-scrollbar">
                    <pre className="text-sm font-mono text-[#D4D4D4] leading-relaxed">
                        {jsonString}
                    </pre>
                </div>
                <div className="p-4 border-t border-[#333] flex justify-end gap-3 bg-transparent">
                    <button
                        onClick={handleDownloadExcel}
                        className="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-6 rounded-lg shadow-sm transition-colors flex items-center gap-2"
                    >
                        <FileSpreadsheet className="w-5 h-5" /> Download FHIR Mapping
                    </button>
                    <button
                        onClick={handleDownload}
                        className="bg-medical-600 hover:bg-medical-700 text-white font-medium py-2 px-6 rounded-lg shadow-sm transition-colors flex items-center gap-2"
                    >
                        <DownloadCloud className="w-5 h-5" /> Download JSON
                    </button>
                </div>
            </div>
        </div>
    );
}
