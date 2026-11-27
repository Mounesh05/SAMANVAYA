import React from 'react';
import { PageHeader } from '../../components/layout/PageHeader';
import { AlgorithmComparisonPanel } from '../code-quality/AlgorithmComparisonPanel';
import { BehavioralCompatibilityPanel } from '../code-quality/BehavioralCompatibilityPanel';
import { RequirementsPanel } from '../code-quality/RequirementsPanel';
import { PRAlgorithmIntelligencePanel } from '../code-quality/PRAlgorithmIntelligencePanel';
import '../code-quality/CodeQuality.css';

/** Initial standalone workspace. Existing authorized APIs and tools remain unchanged. */
export function AlgorithmIntelligencePage() {
  return <>
    <PageHeader title="Algorithm Intelligence" subtitle="Inspect algorithm patterns, complexity, validated workloads and performance trade-offs." />
    <PRAlgorithmIntelligencePanel />
    <details className="cq-advanced">
      <summary>Advanced tools<span>Benchmarks, compatibility and requirements</span></summary>
      <div className="cq-advanced-body cq-panel">
        <AlgorithmComparisonPanel />
        <BehavioralCompatibilityPanel />
        <RequirementsPanel />
      </div>
    </details>
  </>;
}
