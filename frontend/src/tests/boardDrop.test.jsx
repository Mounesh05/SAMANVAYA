/**
 * Board drag and drop: a card dropped into an EMPTY column moves the task.
 * Columns used to be no drop target at all, so dropping into an empty
 * column silently did nothing and no request was sent.
 *
 * jsdom has no layout, so a real pointer drag cannot be simulated here. The
 * tests check the two halves instead: every column registers as a drop target
 * with dnd-kit, and a drop reported on a column moves the task.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { BoardPage } from '../pages/board/BoardPage';
import { boardApi } from '../api/board.api';
import { projectsApi } from '../api/projects.api';
import { useAuthStore } from '../store/useAuthStore';
import { roleUser } from './utils/roleUser';

const dnd = vi.hoisted(() => ({ droppableIds: new Set(), contextProps: null }));
vi.mock('@dnd-kit/core', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useDroppable: (args) => { dnd.droppableIds.add(args.id); return actual.useDroppable(args); },
    DndContext: (props) => { dnd.contextProps = props; return <actual.DndContext {...props} />; },
  };
});
vi.mock('../api/board.api', () => ({ boardApi: { getProjectBoard: vi.fn(), moveItem: vi.fn() } }));
vi.mock('../api/projects.api', () => ({ projectsApi: { list: vi.fn() } }));

const TASK = { id: 'TSK-533075F3', title: 'Set up project structure and README', status: 'todo', priority: 'medium', assignee_id: 'E5' };
const COLUMNS = ['todo', 'in_progress', 'review', 'done', 'blocked'];
const BOARD = { tasks: { columns: COLUMNS.map((id) => ({ id, title: id, items: id === 'todo' ? [TASK] : [] })) } };
const E5 = roleUser('DEVELOPER', { employee_id: 'E5', name: 'Arjun S R', team_id: 'T1' });

let client;
function renderBoard(user) {
  useAuthStore.setState({ user });
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<MemoryRouter><QueryClientProvider client={client}><BoardPage /></QueryClientProvider></MemoryRouter>);
}
const dropOn = (overId, item = TASK) => act(() => {
  dnd.contextProps.onDragEnd({ active: { id: item.id, data: { current: { item } } }, over: { id: overId } });
});

beforeEach(() => {
  vi.clearAllMocks();
  dnd.droppableIds.clear();
  projectsApi.list.mockResolvedValue([{ id: 'PRJ-BFAAEA0A', name: 'Expense Tracker' }]);
  boardApi.getProjectBoard.mockResolvedValue(BOARD);
  boardApi.moveItem.mockResolvedValue({});
});
afterEach(() => { cleanup(); client?.clear(); });

it('registers every column as a drop target, including empty ones', async () => {
  renderBoard(E5);
  await screen.findByText('Set up project structure and README');
  expect([...dnd.droppableIds]).toEqual(expect.arrayContaining(COLUMNS));
});

it('moves the task when it is dropped on an empty column', async () => {
  renderBoard(E5);
  await screen.findByText('Set up project structure and README');
  await dropOn('in_progress');
  await waitFor(() => expect(boardApi.moveItem).toHaveBeenCalledWith('TSK-533075F3', 'task', 'in_progress'));
});

it('does nothing when dropped back on its own column', async () => {
  renderBoard(E5);
  await screen.findByText('Set up project structure and README');
  await dropOn('todo');
  expect(boardApi.moveItem).not.toHaveBeenCalled();
});

it('makes the whole card draggable for its assignee only', async () => {
  renderBoard(E5);
  expect(await screen.findByLabelText(/Set up project structure and README\. Drag to change status/)).toHaveAttribute('role', 'button');
  cleanup(); client?.clear();
  renderBoard(roleUser('DEVELOPER', { employee_id: 'E7', team_id: 'T1' }));
  await screen.findByText('Set up project structure and README');
  expect(screen.queryByLabelText(/Drag to change status/)).not.toBeInTheDocument();
});
