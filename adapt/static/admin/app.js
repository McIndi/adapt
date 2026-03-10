document.addEventListener('DOMContentLoaded', () => {
    // State
    const state = {
        users: [],
        locks: [],
        groups: [],
        permissions: [],
        'api-keys': [],
        'audit-logs': [],
        cache: [],
        currentUser: null
    };

    // Elements
    const views = {
        users: document.getElementById('users-view'),
        locks: document.getElementById('locks-view'),
        groups: document.getElementById('groups-view'),
        permissions: document.getElementById('permissions-view'),
        'api-keys': document.getElementById('api-keys-view'),
        'audit-logs': document.getElementById('audit-logs-view'),
        cache: document.getElementById('cache-view')
    };
    const tables = {
        users: document.querySelector('#users-table tbody'),
        locks: document.querySelector('#locks-table tbody'),
        groups: document.querySelector('#groups-table tbody'),
        permissions: document.querySelector('#permissions-table tbody'),
        'api-keys': document.querySelector('#api-keys-table tbody'),
        'audit-logs': document.querySelector('#audit-logs-table tbody'),
        cache: document.querySelector('#cache-table tbody')
    };
    const modals = {
        user: document.getElementById('user-modal'),
        group: document.getElementById('group-modal'),
        members: document.getElementById('members-modal'),
        permission: document.getElementById('permission-modal'),
        groupPermissions: document.getElementById('group-permissions-modal'),
        showKey: document.getElementById('show-key-modal')
    };
    const forms = {
        user: document.getElementById('add-user-form'),
        group: document.getElementById('add-group-form'),
        permission: document.getElementById('add-permission-form')
    };

    // Member Management Elements
    const membersList = document.getElementById('members-list');
    const addMemberSelect = document.getElementById('add-member-select');
    const addMemberBtn = document.getElementById('add-member-btn');

    // Group Permission Management Elements
    const groupPermissionsList = document.getElementById('group-permissions-list');
    const addGroupPermissionSelect = document.getElementById('add-group-permission-select');
    const addGroupPermissionBtn = document.getElementById('add-group-permission-btn');

    let currentGroupId = null;

    const usernameDisplay = document.getElementById('current-username');

    function csrfHeaders(headers = {}) {
        const token = window.getAdaptCsrfToken ? window.getAdaptCsrfToken() : '';
        if (!token) {
            return headers;
        }
        return { ...headers, 'X-CSRF-Token': token };
    }

    // Init
    init();

    async function init() {
        try {
            await checkAuth();
            setupEventListeners();
            loadUsers();
        } catch (err) {
            console.error(err);
            // Redirect to login
            window.location.href = '/auth/login?next=' + encodeURIComponent(window.location.pathname);
        }
    }

    async function checkAuth() {
        const res = await fetch('/auth/me');
        if (!res.ok) throw new Error('Not authenticated');
        const user = await res.json();
        state.currentUser = user;
        usernameDisplay.textContent = user.username;

        if (!user.is_superuser) {
            alert('Access denied: Superuser privileges required.');
            document.body.innerHTML = '<h1>Access Denied</h1><p>Superuser privileges required.</p>';
            throw new Error('Access denied');
        }
    }

    function setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-item').forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;
                switchTab(tab);
            });
        });

        // Modals
        document.getElementById('add-user-btn').addEventListener('click', () => {
            modals.user.classList.add('active');
        });
        document.getElementById('add-group-btn').addEventListener('click', () => {
            modals.group.classList.add('active');
        });
        document.getElementById('add-permission-btn').addEventListener('click', () => {
            modals.permission.classList.add('active');
        });

        document.querySelectorAll('.close-modal').forEach(btn => {
            btn.addEventListener('click', () => {
                Object.values(modals).forEach(m => m.classList.remove('active'));
            });
        });

        // Forms
        forms.user.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(forms.user);
            const data = Object.fromEntries(formData.entries());
            data.is_superuser = formData.get('is_superuser') === 'on';

            await createUser(data);
            modals.user.classList.remove('active');
            forms.user.reset();
            loadUsers();
        });

        forms.group.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(forms.group);
            const data = Object.fromEntries(formData.entries());

            await createGroup(data);
            modals.group.classList.remove('active');
            forms.group.reset();
            loadGroups();
        });

        forms.permission.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(forms.permission);
            const data = Object.fromEntries(formData.entries());

            await createPermission(data);
            modals.permission.classList.remove('active');
            forms.permission.reset();
            loadPermissions();
        });

        // Members
        addMemberBtn.addEventListener('click', async () => {
            const userId = addMemberSelect.value;
            if (userId && currentGroupId) {
                await addGroupMember(currentGroupId, userId);
            }
        });

        // Group Permissions
        addGroupPermissionBtn.addEventListener('click', async () => {
            const permId = addGroupPermissionSelect.value;
            if (permId && currentGroupId) {
                await addGroupPermission(currentGroupId, permId);
            }
        });

        // Actions
        document.getElementById('clean-locks-btn').addEventListener('click', cleanLocks);
        document.getElementById('logout-btn').addEventListener('click', logout);
    }

    function switchTab(tab) {
        // Update nav
        document.querySelectorAll('.nav-item').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });

        // Update view
        Object.values(views).forEach(el => el.classList.remove('active'));
        views[tab].classList.add('active');

        // Load data
        if (tab === 'users') loadUsers();
        if (tab === 'locks') loadLocks();
        if (tab === 'groups') loadGroups();
        if (tab === 'permissions') loadPermissions();
        if (tab === 'api-keys') loadApiKeys();
        if (tab === 'audit-logs') loadAuditLogs();
        if (tab === 'cache') loadCache();
    }

    // API Calls
    async function loadUsers() {
        const res = await fetch('/admin/users');
        if (res.ok) {
            state.users = await res.json();
            renderUsers();
        }
    }

    async function createUser(data) {
        const res = await fetch('/admin/users', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(data)
        });
        if (!res.ok) {
            const err = await res.json();
            alert(err.detail || 'Failed to create user');
        }
    }

    async function deleteUser(id) {
        if (!confirm('Are you sure you want to delete this user?')) return;
        const res = await fetch(`/admin/users/${id}`, { method: 'DELETE', headers: csrfHeaders() });
        if (res.ok) loadUsers();
        else alert('Failed to delete user');
    }

    async function loadLocks() {
        const res = await fetch('/admin/locks');
        if (res.ok) {
            state.locks = await res.json();
            renderLocks();
        }
    }

    async function releaseLock(id) {
        const res = await fetch(`/admin/locks/${id}`, { method: 'DELETE', headers: csrfHeaders() });
        if (res.ok) loadLocks();
    }

    async function cleanLocks() {
        const res = await fetch('/admin/locks/clean', { method: 'POST', headers: csrfHeaders() });
        if (res.ok) {
            const data = await res.json();
            alert(`Released ${data.released} stale locks`);
            loadLocks();
        }
    }

    async function loadGroups() {
        const res = await fetch('/admin/groups');
        if (res.ok) {
            state.groups = await res.json();
            renderGroups();
        }
    }

    async function createGroup(data) {
        const res = await fetch('/admin/groups', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(data)
        });
        if (!res.ok) {
            const err = await res.json();
            alert(err.detail || 'Failed to create group');
        }
    }

    async function deleteGroup(id) {
        if (!confirm('Are you sure you want to delete this group?')) return;
        const res = await fetch(`/admin/groups/${id}`, { method: 'DELETE', headers: csrfHeaders() });
        if (res.ok) loadGroups();
        else alert('Failed to delete group');
    }

    async function loadPermissions() {
        const res = await fetch('/admin/permissions');
        if (res.ok) {
            state.permissions = await res.json();
            renderPermissions();
        }
    }

    async function createPermission(data) {
        const res = await fetch('/admin/permissions', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(data)
        });
        if (!res.ok) {
            const err = await res.json();
            alert(err.detail || 'Failed to create permission');
        }
    }

    async function deletePermission(id) {
        if (!confirm('Are you sure you want to delete this permission?')) return;
        const res = await fetch(`/admin/permissions/${id}`, { method: 'DELETE', headers: csrfHeaders() });
        if (res.ok) loadPermissions();
        else alert('Failed to delete permission');
    }

    async function openMembersModal(groupId) {
        currentGroupId = groupId;
        modals.members.classList.add('active');

        const res = await fetch(`/admin/groups/${groupId}`);
        let members = [];
        if (res.ok) {
            const group = await res.json();
            members = group.users || [];
        } else {
            console.warn('Could not fetch group members');
        }

        renderMembers(members);
        renderAddMemberSelect(members);
    }

    async function addGroupMember(groupId, userId) {
        const res = await fetch(`/admin/groups/${groupId}/users/${userId}`, { method: 'POST', headers: csrfHeaders() });
        if (res.ok) {
            openMembersModal(groupId); // Reload
        } else {
            alert('Failed to add member');
        }
    }

    async function removeGroupMember(groupId, userId) {
        if (!confirm('Remove user from group?')) return;
        const res = await fetch(`/admin/groups/${groupId}/users/${userId}`, { method: 'DELETE', headers: csrfHeaders() });
        if (res.ok) {
            openMembersModal(groupId); // Reload
        } else {
            alert('Failed to remove member');
        }
    }

    async function openGroupPermissionsModal(groupId) {
        currentGroupId = groupId;
        modals.groupPermissions.classList.add('active');

        // Fetch current group permissions
        const res = await fetch(`/admin/groups/${groupId}/permissions`);
        let currentPerms = [];
        if (res.ok) {
            currentPerms = await res.json();
        } else {
            console.warn('Could not fetch group permissions');
        }

        // Ensure we have all permissions loaded for the select
        if (state.permissions.length === 0) {
            await loadPermissions();
        }

        renderGroupPermissions(currentPerms);
        renderAddGroupPermissionSelect(currentPerms);
    }

    async function addGroupPermission(groupId, permId) {
        const res = await fetch(`/admin/groups/${groupId}/permissions/${permId}`, { method: 'POST', headers: csrfHeaders() });
        if (res.ok) {
            openGroupPermissionsModal(groupId); // Reload
        } else {
            alert('Failed to add permission to group');
        }
    }

    async function removeGroupPermission(groupId, permId) {
        if (!confirm('Remove permission from group?')) return;
        const res = await fetch(`/admin/groups/${groupId}/permissions/${permId}`, { method: 'DELETE', headers: csrfHeaders() });
        if (res.ok) {
            openGroupPermissionsModal(groupId); // Reload
        } else {
            alert('Failed to remove permission from group');
        }
    }

    async function logout() {
        await fetch('/auth/logout', { method: 'POST', headers: csrfHeaders() });
        window.location.reload();
    }

    // Rendering
    function renderUsers() {
        tables.users.innerHTML = state.users.map(user => `
            <tr>
                <td>${user.id}</td>
                <td>${user.username}</td>
                <td><span class="badge" style="background: ${user.is_superuser ? 'var(--primary)' : '#64748b'}">${user.is_superuser ? 'Admin' : 'User'}</span></td>
                <td>${user.is_active ? 'Yes' : 'No'}</td>
                <td>
                    ${user.id !== state.currentUser.id ?
                `<button class="btn danger" onclick="window.deleteUser(${user.id})">Delete</button>` :
                '<span class="text-secondary">Current</span>'}
                </td>
            </tr>
        `).join('');
    }

    function renderLocks() {
        if (state.locks.length === 0) {
            tables.locks.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-secondary)">No active locks</td></tr>';
            return;
        }
        tables.locks.innerHTML = state.locks.map(lock => `
            <tr>
                <td>${lock.id}</td>
                <td>${lock.resource}</td>
                <td>${lock.owner}</td>
                <td>${lock.reason || '-'}</td>
                <td>${new Date(lock.expires_at).toLocaleString()}</td>
                <td>
                    <button class="btn danger" onclick="window.releaseLock(${lock.id})">Release</button>
                </td>
            </tr>
        `).join('');
    }

    function renderGroups() {
        if (!state.groups || state.groups.length === 0) {
            tables.groups.innerHTML = '<tr><td colspan="4" style="text-align:center; color: var(--text-secondary)">No groups found</td></tr>';
            return;
        }
        tables.groups.innerHTML = state.groups.map(group => `
            <tr>
                <td>${group.id}</td>
                <td>${group.name}</td>
                <td>${group.description || '-'}</td>
                <td>
                    <button class="btn secondary" onclick="window.openMembersModal(${group.id})" style="margin-right: 0.5rem;">Members</button>
                    <button class="btn secondary" onclick="window.openGroupPermissionsModal(${group.id})" style="margin-right: 0.5rem;">Permissions</button>
                    <button class="btn danger" onclick="window.deleteGroup(${group.id})">Delete</button>
                </td>
            </tr>
        `).join('');
    }

    function renderPermissions() {
        if (!state.permissions || state.permissions.length === 0) {
            tables.permissions.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--text-secondary)">No permissions found</td></tr>';
            return;
        }
        tables.permissions.innerHTML = state.permissions.map(perm => `
            <tr>
                <td>${perm.id}</td>
                <td>${perm.resource}</td>
                <td>${perm.action}</td>
                <td>${perm.description || '-'}</td>
                <td>
                    <button class="btn danger" onclick="window.deletePermission(${perm.id})">Delete</button>
                </td>
            </tr>
        `).join('');
    }

    function renderMembers(members) {
        if (members.length === 0) {
            membersList.innerHTML = '<li style="padding: 0.5rem; color: var(--text-secondary); text-align: center;">No members</li>';
            return;
        }
        membersList.innerHTML = members.map(user => `
            <li style="padding: 0.5rem; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                <span>${user.username}</span>
                <button class="btn danger small" onclick="window.removeGroupMember(${currentGroupId}, ${user.id})">&times;</button>
            </li>
        `).join('');
    }

    function renderAddMemberSelect(currentMembers) {
        const currentIds = new Set(currentMembers.map(u => u.id));
        const availableUsers = state.users.filter(u => !currentIds.has(u.id));

        addMemberSelect.innerHTML = '<option value="">Select User...</option>' +
            availableUsers.map(user => `<option value="${user.id}">${user.username}</option>`).join('');
    }

    function renderGroupPermissions(currentPerms) {
        if (currentPerms.length === 0) {
            groupPermissionsList.innerHTML = '<li style="padding: 0.5rem; color: var(--text-secondary); text-align: center;">No permissions assigned</li>';
            return;
        }
        groupPermissionsList.innerHTML = currentPerms.map(perm => `
            <li style="padding: 0.5rem; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                <span>${perm.action} on ${perm.resource}</span>
                <button class="btn danger small" onclick="window.removeGroupPermission(${currentGroupId}, ${perm.id})">&times;</button>
            </li>
        `).join('');
    }

    function renderAddGroupPermissionSelect(currentPerms) {
        const currentIds = new Set(currentPerms.map(p => p.id));
        const availablePerms = state.permissions.filter(p => !currentIds.has(p.id));

        addGroupPermissionSelect.innerHTML = '<option value="">Select Permission...</option>' +
            availablePerms.map(perm => `<option value="${perm.id}">${perm.action} on ${perm.resource}</option>`).join('');
    }

    // Expose actions to window for inline onclicks
    window.deleteUser = deleteUser;
    window.releaseLock = releaseLock;
    window.deleteGroup = deleteGroup;
    window.openMembersModal = openMembersModal;
    window.removeGroupMember = removeGroupMember;
    window.deletePermission = deletePermission;
    window.openGroupPermissionsModal = openGroupPermissionsModal;
    window.deletePermission = deletePermission;
    window.openGroupPermissionsModal = openGroupPermissionsModal;
    window.removeGroupPermission = removeGroupPermission;
    window.revokeApiKey = revokeApiKey;

    // --- API Keys Logic ---

    async function loadApiKeys() {
        const res = await fetch('/admin/api-keys');
        if (res.ok) {
            state.apiKeys = await res.json();
            renderApiKeys();
        }
    }

    async function createApiKey(data) {
        const res = await fetch('/admin/api-keys', {
            method: 'POST',
            headers: csrfHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(data)
        });
        if (res.ok) {
            const newKey = await res.json();
            // Show key to user
            document.getElementById('new-api-key-display').textContent = newKey.key;
            document.getElementById('show-key-modal').classList.add('active');
            loadApiKeys();
        } else {
            const err = await res.json();
            alert(err.detail || 'Failed to generate API Key');
        }
    }

    async function revokeApiKey(id) {
        if (!confirm('Revoke this API Key?')) return;
        const res = await fetch(`/admin/api-keys/${id}`, { method: 'DELETE', headers: csrfHeaders() });
        if (res.ok) loadApiKeys();
        else alert('Failed to revoke API Key');
    }

    function renderApiKeys() {
        const tbody = document.querySelector('#api-keys-table tbody');
        if (!state.apiKeys || state.apiKeys.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-secondary)">No API Keys found</td></tr>';
            return;
        }
        tbody.innerHTML = state.apiKeys.map(key => `
            <tr>
                <td>${key.id}</td>
                <td>${key.user_id}</td>
                <td>${key.description || '-'}</td>
                <td>${key.expires_at ? new Date(key.expires_at).toLocaleDateString() : 'Never'}</td>
                <td>${key.last_used_at ? new Date(key.last_used_at).toLocaleString() : 'Never'}</td>
                <td>
                    <button class="btn danger" onclick="window.revokeApiKey(${key.id})">Revoke</button>
                </td>
            </tr>
        `).join('');
    }

    // --- Audit Logs Logic ---

    async function loadAuditLogs() {
        const userId = document.getElementById('filter-user-id').value;
        const action = document.getElementById('filter-action').value;
        const resource = document.getElementById('filter-resource').value;
        const params = new URLSearchParams();
        if (userId) params.append('user_id', userId);
        if (action) params.append('action', action);
        if (resource) params.append('resource', resource);
        const res = await fetch(`/admin/audit-logs?${params}`);
        if (res.ok) {
            state['audit-logs'] = await res.json();
            renderAuditLogs();
        }
    }

    function renderAuditLogs() {
        const tbody = document.querySelector('#audit-logs-table tbody');
        if (!state['audit-logs'] || state['audit-logs'].length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-secondary)">No logs found</td></tr>';
            return;
        }
        tbody.innerHTML = state['audit-logs'].map(log => `
            <tr>
                <td>${new Date(log.timestamp).toLocaleString()}</td>
                <td>${log.user_id || 'Anon'}</td>
                <td>${log.action}</td>
                <td>${log.resource}</td>
                <td>${log.details || '-'}</td>
                <td>${log.ip_address || '-'}</td>
            </tr>
        `).join('');
    }

    // --- Cache Logic ---

    async function loadCache() {
        const res = await fetch('/admin/cache');
        if (res.ok) {
            state.cache = await res.json();
            renderCache();
        }
    }

    function renderCache() {
        const tbody = document.querySelector('#cache-table tbody');
        if (!state.cache || state.cache.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--text-secondary)">No cache entries</td></tr>';
            return;
        }
        tbody.innerHTML = state.cache.map(entry => `
            <tr>
                <td>${entry.key}</td>
                <td>${entry.resource}</td>
                <td>${entry.user || '-'}</td>
                <td>${new Date(entry.expires_at).toLocaleString()}</td>
                <td><button class="btn danger" onclick="deleteCacheEntry(${JSON.stringify(entry.key)}, ${JSON.stringify(entry.resource)})">Delete</button></td>
            </tr>
        `).join('');
    }

    async function deleteCacheEntry(key, resource) {
        const res = await fetch(`/admin/cache/${encodeURIComponent(key)}?resource=${encodeURIComponent(resource)}`, { method: 'DELETE', headers: csrfHeaders() });
        if (res.ok) loadCache();
        else alert('Failed to delete cache entry');
    }

    window.deleteCacheEntry = deleteCacheEntry;

    async function clearCache() {
        if (!confirm('Are you sure you want to clear all cache?')) return;
        const res = await fetch('/admin/cache', { method: 'DELETE', headers: csrfHeaders() });
        if (res.ok) loadCache();
        else alert('Failed to clear cache');
    }

    // --- Event Listeners for New Features ---

    document.getElementById('add-api-key-btn').addEventListener('click', () => {
        // Populate user select
        const select = document.querySelector('select[name="user_id"]');
        select.innerHTML = state.users.map(u => `<option value="${u.id}">${u.username}</option>`).join('');
        document.getElementById('api-key-modal').classList.add('active');
    });

    document.getElementById('add-api-key-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData.entries());
        data.user_id = parseInt(data.user_id);
        if (data.expires_in_days) data.expires_in_days = parseInt(data.expires_in_days);
        else delete data.expires_in_days;

        await createApiKey(data);
        document.getElementById('api-key-modal').classList.remove('active');
        e.target.reset();
    });

    document.getElementById('refresh-audit-btn').addEventListener('click', loadAuditLogs);

    document.getElementById('clear-cache-btn').addEventListener('click', clearCache);

    // Hook into switchTab
    const originalSwitchTab = switchTab;
    switchTab = function (tab) {
        originalSwitchTab(tab);
        if (tab === 'api-keys') loadApiKeys();
        if (tab === 'audit-logs') loadAuditLogs();
        if (tab === 'cache') loadCache();
    };
});
