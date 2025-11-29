import React from 'react';
import { Change, CHANGE_TYPE_CONFIG, getConfidenceColor } from '../../types/graph';
import { EvidencePanel } from './EvidencePanel';
import { ChangeEditor } from './ChangeEditor';

interface ChangeItemProps {
  change: Change;
  proposalStatus: 'pending' | 'approved' | 'rejected';
  isSelected: boolean;
  isEditing: boolean;
  showEvidence: boolean;
  onToggleSelection: () => void;
  onStartEdit: (initialValues: Record<string, any>) => void;
  onSaveEdit: (newValues: Record<string, any>) => void;
  onCancelEdit: () => void;
  onToggleEvidence: () => void;
  onAskAgent: (question: string) => void;
}

export function ChangeItem({
  change,
  proposalStatus,
  isSelected,
  isEditing,
  showEvidence,
  onToggleSelection,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onToggleEvidence,
  onAskAgent,
}: ChangeItemProps) {
  const config = CHANGE_TYPE_CONFIG[change.type];

  const renderProperties = (props: Record<string, any>) => {
    return Object.entries(props)
      .map(([key, value]) => `${key}: ${value}`)
      .join(' · ');
  };

  const renderChangeContent = () => {
    if (change.type === 'add_node') {
      const confidenceColor = getConfidenceColor(change.confidence);
      return (
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 bg-dark-border/50 text-text-muted text-xs rounded">
              {change.entity}
            </span>
            <span className="font-medium text-text-main">{change.label}</span>
            {change.userModified && (
              <span className="text-xs text-amber-500">• edited</span>
            )}
            <span
              className="ml-auto text-sm font-medium"
              style={{ color: confidenceColor }}
            >
              {change.confidence}%
            </span>
          </div>
          <div className="text-sm text-text-muted">
            {renderProperties(change.properties)}
          </div>
        </div>
      );
    }

    if (change.type === 'add_edge') {
      return (
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-text-main">{change.from}</span>
            <span
              className="px-2 py-0.5 text-xs font-medium rounded"
              style={{ backgroundColor: `${config.color}20`, color: config.color }}
            >
              {change.relationship}
            </span>
            <span className="text-text-main">{change.to}</span>
            {change.userModified && (
              <span className="text-xs text-amber-500">• edited</span>
            )}
          </div>
          {change.properties && (
            <div className="text-sm text-text-muted">
              {renderProperties(change.properties)}
            </div>
          )}
        </div>
      );
    }

    if (change.type === 'modify_node') {
      const confidenceColor = getConfidenceColor(change.confidence);
      return (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="px-2 py-0.5 bg-dark-border/50 text-text-muted text-xs rounded">
              {change.entity}
            </span>
            <span className="font-medium text-text-main">{change.label}</span>
            {change.userModified && (
              <span className="text-xs text-amber-500">• edited</span>
            )}
            <span
              className="ml-auto text-sm font-medium"
              style={{ color: confidenceColor }}
            >
              {change.confidence}%
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm border border-dark-border rounded overflow-hidden">
            <div className="p-2 bg-red-950/20 border-r border-dark-border">
              <div className="text-red-400 font-medium mb-1">− Before</div>
              {Object.entries(change.before).map(([key, value]) => (
                <div key={key} className="text-text-muted">
                  {key}: {value?.toString() || 'null'}
                </div>
              ))}
            </div>
            <div className="p-2 bg-green-950/20">
              <div className="text-green-400 font-medium mb-1">+ After</div>
              {Object.entries(change.after).map(([key, value]) => (
                <div key={key} className="text-text-main">
                  {key}: {value?.toString() || 'null'}
                </div>
              ))}
            </div>
          </div>
        </div>
      );
    }

    if (change.type === 'delete_node') {
      return (
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 bg-dark-border/50 text-text-muted text-xs rounded">
              {change.entity}
            </span>
            <span className="font-medium text-text-main line-through">{change.label}</span>
          </div>
          {change.reason && (
            <div className="text-sm text-text-muted">Reason: {change.reason}</div>
          )}
        </div>
      );
    }

    if (change.type === 'delete_edge') {
      return (
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-text-main line-through">{change.from}</span>
            <span
              className="px-2 py-0.5 text-xs font-medium rounded line-through"
              style={{ backgroundColor: `${config.color}20`, color: config.color }}
            >
              {change.relationship}
            </span>
            <span className="text-text-main line-through">{change.to}</span>
          </div>
          {change.reason && (
            <div className="text-sm text-text-muted">Reason: {change.reason}</div>
          )}
        </div>
      );
    }

    if (change.type === 'merge_nodes') {
      const confidenceColor = getConfidenceColor(change.matchConfidence * 100);
      return (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="px-2 py-0.5 bg-dark-border/50 text-text-muted text-xs rounded">
              {change.entity}
            </span>
            <span className="font-medium text-text-main">{change.primaryLabel}</span>
            <span className="text-purple-400 mx-1">⊕</span>
            <span className="font-medium text-text-muted">{change.secondaryLabel}</span>
            {change.userModified && (
              <span className="text-xs text-amber-500">• edited</span>
            )}
            {change.requiresReview && (
              <span className="text-xs text-amber-400 ml-2">⚠ Review Required</span>
            )}
            <span
              className="ml-auto text-sm font-medium"
              style={{ color: confidenceColor }}
            >
              {Math.round(change.matchConfidence * 100)}%
            </span>
          </div>

          {/* Matched Rules */}
          {change.matchedRules && change.matchedRules.length > 0 && (
            <div className="mb-2 text-xs text-purple-400">
              Matched on: {change.matchedRules.join(', ')}
            </div>
          )}

          {/* Three-column view: Primary, Secondary, Merged */}
          <div className="grid grid-cols-3 gap-2 text-sm border border-dark-border rounded overflow-hidden">
            <div className="p-2 bg-blue-950/20 border-r border-dark-border">
              <div className="text-blue-400 font-medium mb-1 text-xs">Primary Node</div>
              <div className="text-text-muted text-xs mb-1">{change.primaryLabel}</div>
              {Object.entries(change.primaryProperties).slice(0, 5).map(([key, value]) => (
                <div key={key} className="text-text-muted text-xs truncate">
                  {key}: {value?.toString() || 'null'}
                </div>
              ))}
              {Object.keys(change.primaryProperties).length > 5 && (
                <div className="text-text-muted text-xs italic">
                  +{Object.keys(change.primaryProperties).length - 5} more...
                </div>
              )}
            </div>

            <div className="p-2 bg-purple-950/20 border-r border-dark-border">
              <div className="text-purple-400 font-medium mb-1 text-xs">New Data</div>
              <div className="text-text-muted text-xs mb-1">{change.secondaryLabel}</div>
              {Object.entries(change.secondaryProperties).slice(0, 5).map(([key, value]) => (
                <div key={key} className="text-text-muted text-xs truncate">
                  {key}: {value?.toString() || 'null'}
                </div>
              ))}
              {Object.keys(change.secondaryProperties).length > 5 && (
                <div className="text-text-muted text-xs italic">
                  +{Object.keys(change.secondaryProperties).length - 5} more...
                </div>
              )}
            </div>

            <div className="p-2 bg-green-950/20">
              <div className="text-green-400 font-medium mb-1 text-xs">→ Merged Result</div>
              <div className="text-text-main text-xs mb-1 font-medium">{change.primaryLabel}</div>
              {Object.entries(change.mergedProperties).slice(0, 5).map(([key, value]) => {
                const isNew = !(key in change.primaryProperties);
                const isChanged = !isNew && change.primaryProperties[key] !== value;
                return (
                  <div
                    key={key}
                    className={`text-xs truncate ${isNew || isChanged ? 'text-green-400' : 'text-text-muted'}`}
                  >
                    {key}: {Array.isArray(value) ? `[${value.join(', ')}]` : value?.toString() || 'null'}
                  </div>
                );
              })}
              {Object.keys(change.mergedProperties).length > 5 && (
                <div className="text-text-muted text-xs italic">
                  +{Object.keys(change.mergedProperties).length - 5} more...
                </div>
              )}
            </div>
          </div>
        </div>
      );
    }

    return null;
  };

  const hasEvidence = 'evidence' in change && change.evidence;

  return (
    <div className="group relative p-3 bg-dark-panel hover:bg-dark-panel/80 border border-dark-border rounded">
      <div className="flex items-start gap-3">
        {proposalStatus === 'pending' && (
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onToggleSelection}
            className="mt-1 w-4 h-4 rounded border-dark-border bg-dark checked:bg-blue-600 focus:ring-2 focus:ring-blue-500 focus:ring-offset-0"
          />
        )}

        <div
          className="flex-shrink-0 w-6 h-6 rounded flex items-center justify-center text-sm font-bold mt-0.5"
          style={{ backgroundColor: `${config.color}20`, color: config.color }}
          title={config.label}
        >
          {config.icon}
        </div>

        <div className="flex-1 min-w-0">
          {isEditing ? (
            <ChangeEditor
              change={change}
              onSave={onSaveEdit}
              onCancel={onCancelEdit}
            />
          ) : (
            <>
              {renderChangeContent()}
              {showEvidence && hasEvidence && (
                <EvidencePanel evidence={(change as any).evidence} />
              )}
            </>
          )}
        </div>

        {!isEditing && proposalStatus === 'pending' && (
          <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
            {(change.type === 'add_node' || change.type === 'add_edge' || change.type === 'modify_node' || change.type === 'merge_nodes') && (
              <button
                onClick={() => {
                  if (change.type === 'add_node') {
                    onStartEdit({ properties: change.properties });
                  } else if (change.type === 'add_edge') {
                    onStartEdit({ properties: change.properties || {} });
                  } else if (change.type === 'modify_node') {
                    onStartEdit({ after: change.after });
                  } else if (change.type === 'merge_nodes') {
                    onStartEdit({ mergedProperties: change.mergedProperties });
                  }
                }}
                className="p-1.5 hover:bg-dark-border rounded text-text-muted hover:text-text-main"
                title="Edit"
              >
                ✎
              </button>
            )}
            {hasEvidence && (
              <button
                onClick={onToggleEvidence}
                className="p-1.5 hover:bg-dark-border rounded text-text-muted hover:text-text-main"
                title="Toggle Evidence"
              >
                ?
              </button>
            )}
            <button
              onClick={() => {
                const label = change.type === 'merge_nodes'
                  ? `merging ${(change as any).primaryLabel} and ${(change as any).secondaryLabel}`
                  : (change as any).label || 'this change';
                onAskAgent(`Tell me more about the evidence for ${label}`);
              }}
              className="p-1.5 hover:bg-dark-border rounded text-text-muted hover:text-text-main"
              title="Ask Agent"
            >
              💬
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
