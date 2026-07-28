<?php
/**
 * User Management — port of the offline app's templates/users/list.html.
 * Lists WordPress users holding an esm_* role, matched to their linked
 * staff record where one exists.
 */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;

$role_colors = [
    'esm_super_admin' => '#ef4444', 'esm_accountant' => '#10b981', 'esm_bursar' => '#3b82f6',
    'esm_teacher' => '#f59e0b', 'esm_parent' => '#c8a951', 'esm_student' => '#e85d26',
];
$role_labels = ESM_Helpers::role_labels();
$role_descriptions = ESM_Helpers::role_descriptions();
?>
<div class="page-header">
    <div><h1><i class="fas fa-users-cog" style="color:var(--primary);"></i> User Management</h1><p>Manage user accounts and Excel Schools role assignments</p></div>
    <div><a href="<?php echo esc_url(admin_url('user-new.php')); ?>" class="btn btn-primary"><i class="fas fa-plus"></i> Add User</a></div>
</div>

<div class="card" style="border-left:4px solid var(--info);margin-bottom:20px;">
    <div class="card-body" style="display:flex;align-items:center;gap:16px;">
        <div style="width:40px;height:40px;background:var(--info);color:#fff;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;"><i class="fas fa-info-circle"></i></div>
        <p style="margin:0;font-size:13px;"><strong>WordPress-managed accounts:</strong> Excel Schools roles are assigned via each user's WordPress profile. Add/edit users under WordPress Admin &rarr; Users.</p>
    </div>
</div>

<div class="card" style="margin-bottom:16px;">
    <div class="card-header"><h3><i class="fas fa-shield-alt" style="color:var(--primary);"></i> Role Definitions</h3></div>
    <div class="card-body">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px;">
            <?php foreach ($role_labels as $role_key => $role_label): ?>
            <div style="border:1px solid var(--border);border-radius:8px;padding:12px;border-left:4px solid <?php echo esc_attr($role_colors[$role_key] ?? '#6b7280'); ?>;">
                <h4 style="margin:0 0 2px;"><?php echo esc_html($role_label); ?></h4>
                <p style="font-size:11px;color:var(--text-light);margin:0;"><?php echo esc_html($role_descriptions[$role_key] ?? ''); ?></p>
            </div>
            <?php endforeach; ?>
        </div>
    </div>
</div>

<div class="card">
    <div class="card-header"><h3>User Accounts</h3></div>
    <div class="table-container">
        <table>
            <thead><tr><th>User</th><th>Username</th><th>Role</th><th>Linked Staff</th></tr></thead>
            <tbody>
                <?php
                $esm_roles = array_keys($role_labels);
                $wp_users = get_users(['role__in' => $esm_roles]);
                if ($wp_users): foreach ($wp_users as $u):
                    $u_role = null;
                    foreach ($esm_roles as $r) { if (in_array($r, (array) $u->roles, true)) { $u_role = $r; break; } }
                    $staff = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$pfx}esm_staff WHERE user_id=%d", $u->ID));
                ?>
                <tr>
                    <td style="display:flex;align-items:center;gap:8px;">
                        <div style="width:32px;height:32px;background:var(--primary);color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;"><?php echo esc_html(strtoupper(substr($u->display_name, 0, 1))); ?></div>
                        <div><?php echo esc_html($u->display_name); ?></div>
                    </td>
                    <td><code style="background:var(--bg);padding:2px 8px;border-radius:4px;font-size:12px;"><?php echo esc_html($u->user_login); ?></code></td>
                    <td><span class="badge" style="background:<?php echo esc_attr($role_colors[$u_role] ?? '#6b7280'); ?>;color:#fff;"><?php echo esc_html($role_labels[$u_role] ?? $u_role); ?></span></td>
                    <td><?php echo $staff ? esc_html($staff->first_name . ' ' . $staff->last_name . ' (' . $staff->employee_number . ')') : '&mdash;'; ?></td>
                </tr>
                <?php endforeach; else: ?>
                <tr><td colspan="4" class="text-center" style="padding:30px;color:var(--text-light);">No Excel Schools users found</td></tr>
                <?php endif; ?>
            </tbody>
        </table>
    </div>
</div>
