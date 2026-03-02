import React, { useState, useEffect, useRef } from 'react';

export function JsonPanel({ step, data, onJsonEdit }) {
    const [localJson, setLocalJson] = useState('');
    const [error, setError] = useState(null);
    const [isEditing, setIsEditing] = useState(false);
    const prevDataRef = useRef(null);

    // Sync external data changes to local state unless user is actively editing
    useEffect(() => {
        const serialized = JSON.stringify(data, null, 2);
        if (!isEditing && prevDataRef.current !== serialized) {
            setLocalJson(serialized);
            setError(null);
            prevDataRef.current = serialized;
        }
    }, [data, isEditing]);

    const handleJsonChange = (e) => {
        setLocalJson(e.target.value);
        setError(null);
    };

    const handleEdit = () => {
        setIsEditing(true);
    };

    const handleCancel = () => {
        setLocalJson(JSON.stringify(data, null, 2));
        setError(null);
        setIsEditing(false);
    };

    const handleSave = () => {
        try {
            const parsed = JSON.parse(localJson);
            setError(null);
            setIsEditing(false);
            if (onJsonEdit) onJsonEdit(parsed);
        } catch (err) {
            setError('Invalid JSON: ' + (err.message || 'parse error'));
        }
    };

    const isEditable = step === 1;

    // We show the full JSON when not editing (per updated requirements).

    return (
        <div className="h-full flex flex-col bg-[#1E1E1E] text-gray-300 font-mono text-sm shadow-inner relative">
            <div className="px-4 py-3 bg-[#252526] border-b border-[#333] flex justify-between items-center">
                <div className="flex items-center gap-3">
                    <h3 className="text-xs uppercase tracking-wider text-gray-400 font-semibold cursor-default">
                        Console & JSON Context
                    </h3>
                    {isEditable && (
                        <span className="px-2 py-0.5 rounded text-[10px] uppercase font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">
                            Editable
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-3">
                    {error && (
                        <span className="text-xs text-red-400">{error}</span>
                    )}
                    <span className="px-2 py-0.5 rounded text-[10px] uppercase font-bold bg-medical-500/20 text-medical-400 border border-medical-500/30">
                        State: {["Waiting", "Reviewing", "Validating", "Ready"][step]}
                    </span>
                    {isEditable && (
                        <div className="ml-2 flex items-center gap-2">
                            {!isEditing ? (
                                <button onClick={handleEdit} className="text-xs px-2 py-1 border rounded bg-gray-800 hover:bg-gray-700">Edit</button>
                            ) : (
                                <>
                                    <button onClick={handleSave} className="text-xs px-2 py-1 border rounded bg-green-700 hover:bg-green-600">Save</button>
                                    <button onClick={handleCancel} className="text-xs px-2 py-1 border rounded bg-gray-800 hover:bg-gray-700">Cancel</button>
                                </>
                            )}
                        </div>
                    )}
                </div>
            </div>

            <div className="flex-1 overflow-hidden relativelex-1 overflow-hidden r">
                <textarea
                    value={localJson}
                    onChange={handleJsonChange}
                    spellCheck={false}
                    readOnly={!(isEditable && isEditing)}
                    className={`w-full h-full box-border bg-transparent text-[#D4D4D4] text-xs leading-relaxed px-10 py-4 resize-none focus:outline-none ${isEditing ? 'focus:ring-1 focus:ring-blue-500/50' : ''} custom-scrollbar`}
                />
            </div>
        </div>
    );
}
