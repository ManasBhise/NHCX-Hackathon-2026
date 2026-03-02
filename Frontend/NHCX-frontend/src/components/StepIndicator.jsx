import React from 'react';
import { UploadCloud, FileEdit, Zap, Download } from 'lucide-react';
import clsx from 'clsx';

const steps = [
    { id: 0, title: 'Upload PDF', icon: UploadCloud },
    { id: 1, title: 'Structured Review', icon: FileEdit },
    { id: 2, title: 'Generate & Validate', icon: Zap },
    { id: 3, title: 'Download Bundle', icon: Download },
];

export function StepIndicator({ currentStep, highestStep = 0, onStepClick }) {
    return (
        <div className="w-full bg-white border-b border-gray-100 px-8 py-5">
            <div className="max-w-4xl mx-auto">
                <div className="flex items-start justify-between relative">

                    {/* Progress Bar Background */}
                    <div className="absolute left-0 top-5 -translate-y-1/2 w-full h-1 bg-gray-100 rounded-full z-0"></div>

                    {/* Active Progress Bar */}
                    <div
                        className="absolute left-0 top-5 -translate-y-1/2 h-1 bg-medical-500 rounded-full z-0 transition-all duration-500 ease-in-out"
                        style={{ width: `${(currentStep / (steps.length - 1)) * 100}%` }}
                    ></div>

                    {steps.map((step, index) => {
                        const Icon = step.icon;
                        const isCompleted = currentStep > step.id;
                        const isCurrent = currentStep === step.id;
                        const isClickable = step.id <= highestStep && onStepClick;

                        return (
                            <div key={step.id} className="relative z-10 flex flex-col items-center gap-2">
                                <button
                                    onClick={() => isClickable && onStepClick(step.id)}
                                    disabled={!isClickable}
                                    className={clsx(
                                        "w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300 shadow-sm border-2 outline-none focus:ring-4 focus:ring-medical-50",
                                        isCompleted
                                            ? "bg-medical-500 border-medical-500 text-white"
                                            : isCurrent
                                                ? "bg-white border-medical-500 text-medical-600 ring-4 ring-medical-50"
                                                : "bg-white border-gray-200 text-gray-400",
                                        isClickable ? "cursor-pointer hover:scale-110" : "cursor-not-allowed opacity-70"
                                    )}
                                    title={isClickable ? `Go back to ${step.title}` : undefined}
                                >
                                    <Icon className="w-5 h-5" />
                                </button>
                                <span
                                    className={clsx(
                                        "text-xs font-medium whitespace-nowrap",
                                        isCurrent || step.id <= highestStep ? "text-gray-900" : "text-gray-500"
                                    )}
                                >
                                    {step.title}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
