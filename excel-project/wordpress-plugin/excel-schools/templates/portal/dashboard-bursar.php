<?php
/** Bursar admissions, finance, and manual-sync dashboard. */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;
$total_students = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_students WHERE status='Active'");
$total_classes = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_classes");
$fees_month = (float) $wpdb->get_var("SELECT COALESCE(SUM(amount),0) FROM {$pfx}esm_fee_payments WHERE YEAR(payment_date)=YEAR(CURDATE()) AND MONTH(payment_date)=MONTH(CURDATE())");
$pending_sync = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_sync_log WHERE sync_status='pending'");
$recent_students = $wpdb->get_results("SELECT s.admission_number,s.first_name,s.last_name,c.name AS class_name FROM {$pfx}esm_students s LEFT JOIN {$pfx}esm_classes c ON c.id=s.class_id WHERE s.status='Active' ORDER BY s.created_at DESC LIMIT 8");
$import_result = get_transient('esm_manual_import_' . get_current_user_id());
if ($import_result !== false) delete_transient('esm_manual_import_' . get_current_user_id());
?>
<div class="page-header">
    <div><h1><i class="fas fa-user-tie" style="color:var(--primary)"></i> Bursar Dashboard</h1><p>Manage admissions, classes, finances, and synchronization.</p></div>
    <div class="actions"><a class="btn btn-primary" href="<?php echo esc_url(home_url('/sms/classes/')); ?>"><i class="fas fa-plus"></i> Create Class</a><a class="btn btn-secondary" href="<?php echo esc_url(admin_url('admin.php?page=excel-schools-sync')); ?>"><i class="fas fa-sync-alt"></i> Sync Center</a></div>
</div>
<div class="stats-grid">
    <div class="stat-card"><div class="icon green"><i class="fas fa-user-graduate"></i></div><div class="info"><h3><?php echo esc_html($total_students); ?></h3><p>Active Students</p></div></div>
    <div class="stat-card"><div class="icon purple"><i class="fas fa-school"></i></div><div class="info"><h3><?php echo esc_html($total_classes); ?></h3><p>Classes</p></div></div>
    <div class="stat-card"><div class="icon yellow"><i class="fas fa-dollar-sign"></i></div><div class="info"><h3>$<?php echo esc_html(number_format($fees_month, 2)); ?></h3><p>Fees This Month</p></div></div>
    <div class="stat-card"><div class="icon red"><i class="fas fa-sync-alt"></i></div><div class="info"><h3><?php echo esc_html($pending_sync); ?></h3><p>Pending Sync Changes</p></div></div>
</div>

<?php if (is_array($import_result)): ?>
<div class="card" style="margin-bottom:20px;border-left:4px solid <?php echo isset($import_result['error']) ? 'var(--danger)' : 'var(--success)'; ?>"><div class="card-body">
<?php if (isset($import_result['error'])): ?><strong>Import failed:</strong> <?php echo esc_html($import_result['error']); ?>
<?php else: ?><strong>Import complete:</strong> <?php echo esc_html((int) ($import_result['imported'] ?? 0)); ?> applied, <?php echo esc_html((int) ($import_result['skipped'] ?? 0)); ?> skipped, <?php echo esc_html((int) ($import_result['failed'] ?? 0)); ?> failed.
<?php endif; ?></div></div>
<?php endif; ?>

<div class="card" style="margin-bottom:20px;border-left:4px solid var(--info)">
    <div class="card-header"><h3><i class="fas fa-file-import"></i> Manual JSON Import</h3></div>
    <div class="card-body">
        <p style="margin-top:0;color:var(--text-light)">Import a JSON file exported by the offline app. Classes and all other supported records are merged by their sync IDs and become available to automatic sync.</p>
        <form method="post" enctype="multipart/form-data">
            <?php wp_nonce_field('esm_portal_json_import', 'esm_import_nonce'); ?>
            <input type="file" name="json_file" accept="application/json,.json" required style="padding:10px;border:1px solid var(--border);border-radius:8px;margin-right:8px">
            <button class="btn btn-primary" type="submit" name="esm_manual_json_import" value="1"><i class="fas fa-upload"></i> Import JSON</button>
        </form>
    </div>
</div>

<div class="card">
    <div class="card-header"><h3>Recent Admissions</h3><a class="btn btn-sm btn-secondary" href="<?php echo esc_url(home_url('/sms/students/')); ?>">View Students</a></div>
    <div class="table-container"><table><thead><tr><th>Admission No.</th><th>Student</th><th>Class</th></tr></thead><tbody>
    <?php if ($recent_students): foreach ($recent_students as $student): ?><tr><td><?php echo esc_html($student->admission_number); ?></td><td><?php echo esc_html($student->first_name . ' ' . $student->last_name); ?></td><td><?php echo esc_html($student->class_name ?: 'Unassigned'); ?></td></tr><?php endforeach; else: ?><tr><td colspan="3">No students admitted.</td></tr><?php endif; ?>
    </tbody></table></div>
</div>
