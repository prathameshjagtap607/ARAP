'use client';

import { useState, useEffect } from 'react';
import { SummaryCard } from "@/components/ui/SummaryCard";
import CompetencyTable from "@/components/tables/CompetencyTable";
import CompetencyForm from "@/components/forms/CompetencyForm";
import { getCompetencies, deleteCompetency } from "@/lib/api/competencies";
import { apiFetch } from "@/lib/api";
import { createUser } from "@/lib/api/dashboards";
import { useAuth } from "@/context/AuthContext";
import type { Competency } from '@/lib/types/competency';

interface WorkspaceUser {
  id: string;
  email: string;
  role: string;
  created_at: string;
}

type Tab = 'users' | 'competencies';

const TABS: { id: Tab; label: string }[] = [
  { id: 'users', label: 'Users' },
  { id: 'competencies', label: 'Competencies' },
];

export default function AdminPage() {
  const { user: currentUser } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>('users');
  const [competencies, setCompetencies] = useState<Competency[]>([]);
  const [selectedCompetency, setSelectedCompetency] = useState<Competency | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Users state
  const [users, setUsers] = useState<WorkspaceUser[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [showCreateUserForm, setShowCreateUserForm] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newRole, setNewRole] = useState<'user' | 'admin'>('user');
  const [newPassword, setNewPassword] = useState('');
  const [createUserLoading, setCreateUserLoading] = useState(false);
  const [createUserError, setCreateUserError] = useState<string | null>(null);
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editingRole, setEditingRole] = useState<'user' | 'admin'>('user');
  const [userActionError, setUserActionError] = useState<string | null>(null);
  const [userActionLoadingId, setUserActionLoadingId] = useState<string | null>(null);

  const loadUsers = async () => {
    setUsersLoading(true);
    try {
      const data = await apiFetch<{ items: WorkspaceUser[]; total_count: number }>('/users');
      setUsers(data.items || []);
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setUsersLoading(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateUserError(null);
    setCreateUserLoading(true);
    try {
      const created = await createUser({ email: newEmail, role: newRole, password: newPassword });
      setUsers((prev) => [
        { id: created.id, email: created.email, role: created.role, created_at: created.createdAt },
        ...prev,
      ]);
      setNewEmail('');
      setNewRole('user');
      setNewPassword('');
      setShowCreateUserForm(false);
    } catch (err) {
      setCreateUserError(err instanceof Error ? err.message : 'Failed to create user');
    } finally {
      setCreateUserLoading(false);
    }
  };

  const startEditUser = (u: WorkspaceUser) => {
    setUserActionError(null);
    setEditingUserId(u.id);
    setEditingRole(u.role === 'admin' ? 'admin' : 'user');
  };

  const cancelEditUser = () => {
    setEditingUserId(null);
  };

  const saveEditUser = async (userId: string) => {
    setUserActionError(null);
    setUserActionLoadingId(userId);
    try {
      const updated = await apiFetch<{ id: string; email: string; role: string; created_at: string }>(
        `/users/${userId}`,
        { method: 'PATCH', body: JSON.stringify({ role: editingRole }) }
      );
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role: updated.role } : u)));
      setEditingUserId(null);
    } catch (err) {
      setUserActionError(err instanceof Error ? err.message : 'Failed to update user');
    } finally {
      setUserActionLoadingId(null);
    }
  };

  const handleDeleteUser = async (userId: string) => {
    if (!confirm('Delete this user? This cannot be undone.')) return;
    setUserActionError(null);
    setUserActionLoadingId(userId);
    try {
      await apiFetch(`/users/${userId}`, { method: 'DELETE' });
      setUsers((prev) => prev.filter((u) => u.id !== userId));
    } catch (err) {
      setUserActionError(err instanceof Error ? err.message : 'Failed to delete user');
    } finally {
      setUserActionLoadingId(null);
    }
  };

  const loadCompetencies = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCompetencies();
      setCompetencies(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load competencies');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCompetencies();
    loadUsers();
  }, []);

  const handleDelete = async (id: string) => {
    try {
      await deleteCompetency(id);
      setCompetencies(competencies.filter(c => c.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete competency');
    }
  };

  const handleEdit = (competency: Competency) => {
    setSelectedCompetency(competency);
    setIsCreating(true);
  };

  const handleFormSuccess = () => {
    setIsCreating(false);
    setSelectedCompetency(null);
    loadCompetencies();
  };

  if (isCreating) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-slate-800">
            {selectedCompetency ? 'Edit Competency' : 'Create Competency'}
          </h1>
          <button
            onClick={() => {
              setIsCreating(false);
              setSelectedCompetency(null);
            }}
            className="text-sm text-slate-600 hover:text-slate-900"
          >
            Back
          </button>
        </div>
        <CompetencyForm
          competency={selectedCompetency ?? undefined}
          onSuccess={handleFormSuccess}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-800">Admin</h1>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <SummaryCard label="Organisations" value="—" />
        <SummaryCard label="Total Users" value={usersLoading ? '—' : users.length} />
        <SummaryCard label="Active Orgs" value="—" />
      </div>

      {/* Tab bar */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-slate-800 text-slate-900'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className={`space-y-4 ${activeTab === 'users' ? '' : 'hidden'}`}>
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-800">Users</h2>
          <button
            onClick={() => setShowCreateUserForm((prev) => !prev)}
            className="px-4 py-2 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800 text-sm"
          >
            {showCreateUserForm ? 'Cancel' : '+ Create User'}
          </button>
        </div>

        {showCreateUserForm && (
          <form
            onSubmit={handleCreateUser}
            className="rounded-lg border border-slate-200 bg-slate-50 p-4 flex flex-wrap gap-3 items-end"
          >
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-slate-600">Email</label>
              <input
                type="email"
                required
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className="px-3 py-2 text-sm border border-slate-300 rounded"
                placeholder="name@company.com"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-slate-600">Role</label>
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value as 'user' | 'admin')}
                className="px-3 py-2 text-sm border border-slate-300 rounded"
              >
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-slate-600">Temporary Password</label>
              <input
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="px-3 py-2 text-sm border border-slate-300 rounded"
                placeholder="min 8 characters"
              />
            </div>
            <button
              type="submit"
              disabled={createUserLoading}
              className="px-4 py-2 text-sm font-medium rounded bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {createUserLoading ? 'Creating…' : 'Create'}
            </button>
            {createUserError && (
              <p className="text-sm text-red-600 w-full">{createUserError}</p>
            )}
          </form>
        )}

        {userActionError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
            <p className="text-sm font-medium text-red-900">{userActionError}</p>
          </div>
        )}

        {usersLoading ? (
          <div className="text-center py-8">
            <p className="text-slate-600">Loading users...</p>
          </div>
        ) : users.length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            <p>No users found</p>
          </div>
        ) : (
          <div className="rounded-lg border border-slate-200 bg-white overflow-hidden overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">Email</th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">Role</th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">Joined</th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const isSelf = currentUser?.id === u.id;
                  const isSuperAdmin = u.role === 'super_admin';
                  const isEditing = editingUserId === u.id;
                  const isBusy = userActionLoadingId === u.id;

                  return (
                    <tr key={u.id} className="border-b border-slate-200 hover:bg-slate-50">
                      <td className="px-6 py-4 text-slate-900 font-medium">{u.email}</td>
                      <td className="px-6 py-4">
                        {isEditing ? (
                          <select
                            value={editingRole}
                            onChange={(e) => setEditingRole(e.target.value as 'user' | 'admin')}
                            className="px-2 py-1 text-sm border border-slate-300 rounded"
                          >
                            <option value="user">User</option>
                            <option value="admin">Admin</option>
                          </select>
                        ) : (
                          <span
                            className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
                              u.role === 'admin' ? 'bg-green-100 text-green-900' : 'bg-blue-100 text-blue-900'
                            }`}
                          >
                            {u.role.charAt(0).toUpperCase() + u.role.slice(1)}
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-slate-700">
                        {new Date(u.created_at).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                        })}
                      </td>
                      <td className="px-6 py-4">
                        {isSuperAdmin ? (
                          <span className="text-xs text-slate-400">—</span>
                        ) : isEditing ? (
                          <div className="flex gap-2">
                            <button
                              onClick={() => saveEditUser(u.id)}
                              disabled={isBusy}
                              className="text-xs text-white bg-slate-900 rounded px-2 py-1 hover:bg-slate-800 disabled:opacity-50"
                            >
                              {isBusy ? 'Saving…' : 'Save'}
                            </button>
                            <button
                              onClick={cancelEditUser}
                              disabled={isBusy}
                              className="text-xs text-slate-600 border border-slate-200 rounded px-2 py-1 hover:border-slate-400"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <div className="flex gap-2">
                            <button
                              onClick={() => startEditUser(u)}
                              disabled={isSelf || isBusy}
                              title={isSelf ? "You can't edit your own role" : undefined}
                              className="text-xs text-slate-600 hover:text-slate-900 border border-slate-200 rounded px-2 py-1 hover:border-slate-400 disabled:opacity-40 disabled:cursor-not-allowed"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleDeleteUser(u.id)}
                              disabled={isSelf || isBusy}
                              title={isSelf ? "You can't delete your own account" : undefined}
                              className="text-xs text-red-600 hover:text-red-800 border border-red-200 rounded px-2 py-1 hover:border-red-400 disabled:opacity-40 disabled:cursor-not-allowed"
                            >
                              {isBusy ? 'Deleting…' : 'Delete'}
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className={`space-y-4 ${activeTab === 'competencies' ? '' : 'hidden'}`}>
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-800">Competencies</h2>
          <button
            onClick={() => {
              setSelectedCompetency(null);
              setIsCreating(true);
            }}
            className="px-4 py-2 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800 text-sm"
          >
            Add Competency
          </button>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
            <p className="text-sm font-medium text-red-900">{error}</p>
          </div>
        )}

        {loading ? (
          <div className="text-center py-12">
            <p className="text-slate-600">Loading competencies...</p>
          </div>
        ) : (
          <CompetencyTable
            competencies={competencies}
            onDelete={handleDelete}
            onEdit={handleEdit}
          />
        )}
      </div>

      <p className="text-xs text-slate-400">
        Organisation & user management — Phase 1. Competency management — Phase 2.
      </p>
    </div>
  );
}
