import React, { useState, useEffect } from 'react';
import { ShieldPlus } from 'lucide-react';

export function TopNav() {
    const [healthy, setHealthy] = useState(true);

    useEffect(() => {
        const check = () => {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
            
            fetch('http://localhost:8000/health', { signal: controller.signal })
                .then(res => {
                    clearTimeout(timeoutId);
                    if (res.ok) {
                        setHealthy(true);
                    } else {
                        setHealthy(false);
                    }
                })
                .catch(() => {
                    clearTimeout(timeoutId);
                    setHealthy(false);
                });
        };
        // initial check
        check();
        // poll every 10s
        const id = setInterval(check, 10000);
        return () => clearInterval(id);
    }, []);

    return (
        <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between shadow-sm">
            <div className="flex items-center gap-3">
                <div className="p-2 bg-medical-50 rounded-lg">
                    <ShieldPlus className="w-6 h-6 text-medical-600" />
                </div>
                <h1 className="text-xl font-semibold text-gray-900 tracking-tight">
                    NHCX FHIR Insurance Plan Utility
                </h1>
            </div>
            <div className="flex items-center gap-4 text-sm text-gray-500">
                <span>Compliance Validation Tool</span>
                <div className="h-4 w-px bg-gray-300"></div>
                <span className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${healthy ? 'bg-green-500' : 'bg-red-500'}`}></span>
                    {healthy ? 'System Ready' : 'Backend Unreachable'}
                </span>
            </div>
        </header>
    );
}
