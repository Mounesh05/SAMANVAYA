import React from 'react';
import { OperationsHistory } from '../devops/OperationsHistory';

export function DeploymentsPage() {
  return <OperationsHistory kind="deployments" />;
}
