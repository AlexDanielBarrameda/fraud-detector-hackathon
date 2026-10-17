import React from 'react';
import { CheckCircleIcon } from '@solar-icons/react/linear';

export default function ActionList({ actions = [] }) {
  return (
    <section className="block" aria-labelledby="actions-heading">
      <div className="section-head">
        <h3 id="actions-heading" className="eyebrow">Recommended actions</h3>
        <span className="section-meta">{actions.length} steps</span>
      </div>

      {actions.length > 0 && (
        <ol className="action-list">
          {actions.map((action, i) => (
            <li key={action} className="action">
              <span className="action-index" aria-hidden="true">
                {String(i + 1).padStart(2, '0')}
              </span>
              <CheckCircleIcon size={16} className="action-icon" aria-hidden="true" />
              <span>{action}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
