import React, { useState } from 'react';
import { Change } from '../../types/graph';

interface ChangeEditorProps {
  change: Change;
  onSave: (newValues: Record<string, any>) => void;
  onCancel: () => void;
}

export function ChangeEditor({ change, onSave, onCancel }: ChangeEditorProps) {
  const getEditableProperties = (): Record<string, any> => {
    if (change.type === 'add_node') {
      return change.properties;
    } else if (change.type === 'add_edge') {
      return change.properties || {};
    } else if (change.type === 'modify_node') {
      return change.after;
    }
    return {};
  };

  const [values, setValues] = useState<Record<string, any>>(getEditableProperties());

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (change.type === 'add_node') {
      onSave({ properties: values });
    } else if (change.type === 'add_edge') {
      onSave({ properties: values });
    } else if (change.type === 'modify_node') {
      onSave({ after: values });
    }
  };

  const handleChange = (key: string, value: string) => {
    setValues((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  return (
    <form onSubmit={handleSubmit} className="mt-2 p-3 bg-dark-panel/50 border border-dark-border rounded">
      <div className="space-y-2">
        {Object.entries(values).map(([key, value]) => (
          <div key={key} className="flex items-center gap-2">
            <label className="text-sm text-text-muted w-24 flex-shrink-0">{key}:</label>
            <input
              type="text"
              value={value?.toString() || ''}
              onChange={(e) => handleChange(key, e.target.value)}
              className="flex-1 px-2 py-1 bg-dark text-text-main border border-dark-border rounded text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
        ))}
      </div>
      <div className="flex gap-2 mt-3">
        <button
          type="submit"
          className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium"
        >
          Save
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1 bg-transparent border border-dark-border hover:border-text-muted text-text-muted rounded text-sm"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
