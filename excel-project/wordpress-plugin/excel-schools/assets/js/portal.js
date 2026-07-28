/**
 * ESM Frontend Portal JavaScript
 * Handles staff user management, modal dialogs, and portal interactions.
 * Users are staff-only; roles are allocated to staff members.
 * Version: 2.0.0 | Author: Valentine T Mabheka
 */
(function($) {
    'use strict';
    if (typeof ESM === 'undefined') return;

    var A = ESM.ajax, N = ESM.nonce;

    // Staff-only roles for user management
    var STAFF_ROLES = {
        esm_super_admin: 'Super Admin',
        esm_accountant: 'Accountant',
        esm_bursar: 'Bursar',
        esm_teacher: 'Teacher'
    };

    /* ─── Helpers ──────────────────────────────────────────────────── */

    function esc(s) {
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(s || ''));
        return d.innerHTML;
    }

    function post(data, done) {
        data.nonce = N;
        $.post(A, data, function(r) { done(r); }).fail(function() { alert('Network error.'); });
    }

    /* ─── User Management ──────────────────────────────────────────── */

    function loadUsers() {
        var tb = $('#esm-utb');
        if (!tb.length) return;
        tb.html('<tr><td colspan="6" style="text-align:center;padding:24px;color:#6b7280"><i class="fas fa-spinner fa-spin"></i> Loading users…</td></tr>');
        post({action:'esm_portal_user_list'}, function(r) {
            if (!r.success) { tb.html('<tr><td colspan="6">Error loading users.</td></tr>'); return; }
            var users = r.data;
            if (!users || !users.length) { tb.html('<tr><td colspan="6" style="text-align:center;color:#6b7280;padding:24px">No staff user accounts found.</td></tr>'); return; }

            // Filter to only show staff-role users
            var staffUsers = users.filter(function(u) { return STAFF_ROLES[u.role]; });
            if (!staffUsers.length) { tb.html('<tr><td colspan="6" style="text-align:center;color:#6b7280;padding:24px">No staff user accounts found.</td></tr>'); return; }

            var h = '';
            var badgeMap = {esm_super_admin:'bdg-d',esm_accountant:'bdg-s',esm_bursar:'bdg-i',esm_teacher:'bdg-w'};
            staffUsers.forEach(function(u) {
                var bc = badgeMap[u.role] || 'bdg-i';
                h += '<tr>';
                h += '<td>' + (u.link_type === 'Staff' ? '<i class="fas fa-chalkboard-teacher" style="color:var(--primary)"></i> ' + esc(u.link_name) : '<span style="color:#9ca3af">Unlinked</span>') + '</td>';
                h += '<td style="font-weight:600">' + esc(u.username) + '</td>';
                h += '<td><span class="bdg ' + bc + '">' + esc(STAFF_ROLES[u.role] || u.role_label) + '</span></td>';
                h += '<td>' + (u.active ? '<span class="bdg bdg-s">Active</span>' : '<span class="bdg bdg-d">Inactive</span>') + '</td>';
                h += '<td style="font-size:12px;color:#6b7280">' + esc(u.position || '—') + '</td>';
                h += '<td><button class="btn btn-sm btn-s eu-btn" data-uid="'+u.id+'" data-urole="'+esc(u.role)+'" data-uact="'+u.active+'"><i class="fas fa-edit"></i></button> ';
                h += '<button class="btn btn-sm btn-d du-btn" data-uid="'+u.id+'" data-uname="'+esc(u.username)+'"><i class="fas fa-trash"></i></button></td>';
                h += '</tr>';
            });
            tb.html(h);
        });
    }

    function openUserModal(edit) {
        var m = $('#esm-umodal');
        m.find('#um-title').text(edit ? 'Edit Staff User' : 'Add Staff User');
        m.find('#um-form')[0].reset();
        m.find('#um-id').val(edit ? edit.uid : '');
        m.find('#um-role').html('');
        Object.keys(STAFF_ROLES).forEach(function(k) {
            m.find('#um-role').append('<option value="'+k+'">'+STAFF_ROLES[k]+'</option>');
        });
        m.find('#um-role').val(edit ? edit.urole : 'esm_teacher');
        m.find('#um-active').prop('checked', edit ? edit.uact : true);
        m.find('#um-pw').attr('placeholder', edit ? 'Leave blank to keep current' : 'Min 6 characters');
        m.find('#um-pw').prop('required', !edit);
        m.find('#um-link-group').hide();
        m.addClass('show');
    }

    function closeUserModal() { $('#esm-umodal').removeClass('show'); }

    function loadLinkOptions(type) {
        var sel = $('#um-link-id');
        sel.html('<option value="">— Select —</option>');
        if (!type || type === 'none') { $('#um-link-group').hide(); return; }
        $('#um-link-group').show();
        $.get(A, {action:'esm_get_link_profiles', nonce:N, type:type}, function(r) {
            if (r.success && r.data) {
                r.data.forEach(function(p) { sel.append('<option value="'+p.id+'">'+esc(p.label)+'</option>'); });
            }
        });
    }

    function initUserMgmt() {
        if (ESM.page !== 'users') return;
        loadUsers();

        // Add user
        $(document).on('click', '#esm-add-btn', function() { openUserModal(null); });

        // Edit user
        $(document).on('click', '.eu-btn', function() {
            openUserModal({uid:$(this).data('uid'), urole:$(this).data('urole'), uact:$(this).data('uact')});
        });

        // Delete user
        $(document).on('click', '.du-btn', function() {
            if (!confirm('Delete user "' + $(this).data('uname') + '"?')) return;
            post({action:'esm_portal_user_delete', user_id:$(this).data('uid')}, function(r) {
                if (r.success) loadUsers(); else alert(r.data || 'Error.');
            });
        });

        // Save user
        $(document).on('submit', '#um-form', function(e) {
            e.preventDefault();
            var id = $('#um-id').val();
            var a = id ? 'esm_portal_user_edit' : 'esm_portal_user_add';
            var d = {
                action: a, username: $('#um-uname').val(), password: $('#um-pw').val(),
                email: $('#um-email').val(), role: $('#um-role').val(),
                active: $('#um-active').is(':checked') ? '1' : '',
                link_type: $('#um-link-type').val(), link_id: $('#um-link-id').val(),
            };
            if (id) d.user_id = id;
            if (id) d.new_password = d.password;
            post(d, function(r) {
                if (r.success) { closeUserModal(); loadUsers(); }
                else alert(r.data || 'Error saving user.');
            });
        });

        // Link type change
        $(document).on('change', '#um-link-type', function() { loadLinkOptions($(this).val()); });

        // Close modal
        $(document).on('click', '.um-close', closeUserModal);
        $(document).on('click', '#esm-umodal', function(e) { if ($(e.target).is('#esm-umodal')) closeUserModal(); });
    }

    /* ─── Init ─────────────────────────────────────────────────────── */

    $(document).ready(function() {
        initUserMgmt();
    });

})(jQuery);
