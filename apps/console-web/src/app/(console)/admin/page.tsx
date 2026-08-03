'use client';

import { useState, useEffect } from 'react';
import { SummaryCard } from "@/components/ui/SummaryCard";
import CompetencyTable from "@/components/tables/CompetencyTable";
import CompetencyForm from "@/components/forms/CompetencyForm";
import { getCompetencies, deleteCompetency } from "@/lib/api/competencies";
import { apiFetch } from "@/lib/api";
import { createUser } from "@/lib/api/dashboards";
import type { Competency } from '@/lib/types/competency';

interface WorkspaceUser {
  id: string;
  email: string;
  role: string;
  created_at: string;
}

export default function AdminPage() {
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

      <div className="space-y-4">
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
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-slate-200 hover:bg-slate-50">
                    <td className="px-6 py-4 text-slate-900 font-medium">{u.email}</td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
                          u.role === 'admin' ? 'bg-green-100 text-green-900' : 'bg-blue-100 text-blue-900'
                        }`}
                      >
                        {u.role.charAt(0).toUpperCase() + u.role.slice(1)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      {new Date(u.created_at).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="space-y-4">
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
