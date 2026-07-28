<?php
/** Super-admin school overview and report downloads. */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;
$stats = [
    'students' => (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_students WHERE status='Active'"),
    'staff' => (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_staff WHERE status='Active'"),
    'classes' => (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_classes"),
    'fees' => (float) $wpdb->get_var("SELECT COALESCE(SUM(amount),0) FROM {$pfx}esm_fee_payments WHERE YEAR(payment_date)=YEAR(CURDATE()) AND MONTH(payment_date)=MONTH(CURDATE())"),
    'invoices' => (float) $wpdb->get_var("SELECT COALESCE(SUM(total_amount),0) FROM {$pfx}esm_invoices WHERE status IN ('Unpaid','Partially Paid','Overdue')"),
    'pending_sync' => (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_sync_log WHERE sync_status='pending'"),
];
$by_class = $wpdb->get_results("SELECT c.name,COUNT(s.id) AS students FROM {$pfx}esm_classes c LEFT JOIN {$pfx}esm_students s ON s.class_id=c.id AND s.status='Active' GROUP BY c.id ORDER BY c.name");
$recent_payments = $wpdb->get_results("SELECT p.receipt_number,p.amount,p.payment_date,CONCAT(s.first_name,' ',s.last_name) AS student_name FROM {$pfx}esm_fee_payments p LEFT JOIN {$pfx}esm_students s ON s.id=p.student_id ORDER BY p.payment_date DESC,p.id DESC LIMIT 8");
?>
<div class="page-header">
    <div><h1><i class="fas fa-chart-line" style="color:var(--primary)"></i> School Overview</h1><p>Administration dashboard with whole-school operational and financial reporting.</p></div>
    <div class="actions"><a class="btn btn-primary" href="<?php echo esc_url(home_url('/sms/reports/?download=all')); ?>"><i class="fas fa-download"></i> Download All Reports</a></div>
</div>
<div class="stats-grid">
    <div class="stat-card"><div class="icon green"><i class="fas fa-user-graduate"></i></div><div class="info"><h3><?php echo esc_html($stats['students']); ?></h3><p>Active Students</p></div></div>
    <div class="stat-card"><div class="icon blue"><i class="fas fa-chalkboard-teacher"></i></div><div class="info"><h3><?php echo esc_html($stats['staff']); ?></h3><p>Active Staff</p></div></div>
    <div class="stat-card"><div class="icon purple"><i class="fas fa-school"></i></div><div class="info"><h3><?php echo esc_html($stats['classes']); ?></h3><p>Classes</p></div></div>
    <div class="stat-card"><div class="icon yellow"><i class="fas fa-dollar-sign"></i></div><div class="info"><h3>$<?php echo esc_html(number_format($stats['fees'], 2)); ?></h3><p>Fees This Month</p></div></div>
    <div class="stat-card"><div class="icon red"><i class="fas fa-file-invoice-dollar"></i></div><div class="info"><h3>$<?php echo esc_html(number_format($stats['invoices'], 2)); ?></h3><p>Outstanding Invoices</p></div></div>
    <div class="stat-card"><div class="icon orange"><i class="fas fa-sync-alt"></i></div><div class="info"><h3><?php echo esc_html($stats['pending_sync']); ?></h3><p>Pending Sync Changes</p></div></div>
</div>
<div class="card" style="margin-bottom:20px">
    <div class="card-header"><h3>Reports</h3><a class="btn btn-sm btn-secondary" href="<?php echo esc_url(home_url('/sms/reports/')); ?>">View Reports</a></div>
    <div class="card-body" style="display:flex;gap:10px;flex-wrap:wrap">
        <?php foreach (['students'=>'Student Report','staff'=>'Staff Report','fees'=>'Fee Report','exams'=>'Exam Report'] as $key=>$label): ?>
        <a class="btn btn-secondary" href="<?php echo esc_url(home_url('/sms/reports/?download=' . $key)); ?>"><i class="fas fa-download"></i> <?php echo esc_html($label); ?></a>
        <?php endforeach; ?>
    </div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
    <div class="card"><div class="card-header"><h3>Enrollment by Class</h3></div><div class="table-container"><table><thead><tr><th>Class</th><th>Students</th></tr></thead><tbody><?php foreach ($by_class as $row): ?><tr><td><?php echo esc_html($row->name); ?></td><td><?php echo esc_html($row->students); ?></td></tr><?php endforeach; ?></tbody></table></div></div>
    <div class="card"><div class="card-header"><h3>Recent Payments</h3></div><div class="table-container"><table><thead><tr><th>Receipt</th><th>Student</th><th>Amount</th></tr></thead><tbody><?php if ($recent_payments): foreach ($recent_payments as $row): ?><tr><td><?php echo esc_html($row->receipt_number); ?></td><td><?php echo esc_html($row->student_name ?: '-'); ?></td><td>$<?php echo esc_html(number_format($row->amount, 2)); ?></td></tr><?php endforeach; else: ?><tr><td colspan="3">No payments recorded.</td></tr><?php endif; ?></tbody></table></div></div>
</div>
