<?php
/**
 * Staff list — direct port of the offline app's templates/staff/list.html.
 */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;

$search = sanitize_text_field($_GET['search'] ?? '');
$dept_f = sanitize_text_field($_GET['department'] ?? '');

$where = ['1=1']; $params = [];
if ($search) {
    $where[] = "(employee_number LIKE %s OR first_name LIKE %s OR last_name LIKE %s)";
    $like = '%' . $wpdb->esc_like($search) . '%';
    $params = array_merge($params, [$like, $like, $like]);
}
if ($dept_f) { $where[] = "department = %s"; $params[] = $dept_f; }

$sql = "SELECT * FROM {$pfx}esm_staff WHERE " . implode(' AND ', $where) . " ORDER BY last_name ASC LIMIT 200";
$staff_rows = $params ? $wpdb->get_results($wpdb->prepare($sql, $params)) : $wpdb->get_results($sql);
$departments = $wpdb->get_col("SELECT DISTINCT department FROM {$pfx}esm_staff WHERE department IS NOT NULL AND department != '' ORDER BY department");
?>
<div class="page-header">
    <div><h1>Staff</h1><p>Manage staff members and teachers</p></div>
    <?php if ($role === 'esm_super_admin'): ?>
    <a href="<?php echo esc_url(home_url('/sms/staff/?action=add')); ?>" class="btn btn-primary"><i class="fas fa-plus"></i> Add Staff</a>
    <?php endif; ?>
</div>

<div class="filter-bar" style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;align-items:center;">
    <form method="GET" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
        <input type="text" name="search" class="form-control" placeholder="Search staff..." value="<?php echo esc_attr($search); ?>" style="min-width:250px;">
        <select name="department" class="form-control">
            <option value="">All Departments</option>
            <?php foreach ($departments as $d): ?>
            <option value="<?php echo esc_attr($d); ?>" <?php selected($dept_f, $d); ?>><?php echo esc_html($d); ?></option>
            <?php endforeach; ?>
        </select>
        <button type="submit" class="btn btn-primary"><i class="fas fa-search"></i></button>
        <a href="<?php echo esc_url(home_url('/sms/staff/')); ?>" class="btn btn-secondary"><i class="fas fa-times"></i></a>
    </form>
</div>

<div class="card">
    <div class="table-container">
        <table>
            <thead><tr><th>Emp No.</th><th>Name</th><th>Department</th><th>Position</th><th>Phone</th><th>Status</th></tr></thead>
            <tbody>
                <?php if ($staff_rows): foreach ($staff_rows as $s): ?>
                <tr>
                    <td><strong><?php echo esc_html($s->employee_number); ?></strong></td>
                    <td><?php echo esc_html($s->first_name . ' ' . $s->last_name); ?></td>
                    <td><?php echo esc_html($s->department ?: '-'); ?></td>
                    <td><?php echo esc_html($s->position ?: '-'); ?></td>
                    <td><?php echo esc_html($s->phone ?: '-'); ?></td>
                    <td><span class="badge <?php echo $s->status === 'Active' ? 'badge-success' : 'badge-danger'; ?>"><?php echo esc_html($s->status); ?></span></td>
                </tr>
                <?php endforeach; else: ?>
                <tr><td colspan="6" class="text-center" style="padding:40px;color:var(--text-light);">No staff found</td></tr>
                <?php endif; ?>
            </tbody>
        </table>
    </div>
</div>
