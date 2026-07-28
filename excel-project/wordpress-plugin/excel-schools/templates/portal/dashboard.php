<?php
/**
 * Dashboard — direct port of the offline app's templates/dashboard/index.html,
 * pulling the same stats/recent-records shape from the WordPress esm_* tables.
 */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;

$total_students = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_students WHERE status='Active'");
$total_staff    = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_staff WHERE status='Active'");
$fees_month     = (float) $wpdb->get_var("SELECT COALESCE(SUM(amount),0) FROM {$pfx}esm_fee_payments WHERE YEAR(payment_date)=YEAR(CURDATE()) AND MONTH(payment_date)=MONTH(CURDATE())");
$pending_sync   = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_sync_log WHERE sync_status='pending'");

$recent_students = $wpdb->get_results("SELECT s.*, c.name AS class_name FROM {$pfx}esm_students s LEFT JOIN {$pfx}esm_classes c ON c.id = s.class_id WHERE s.status='Active' ORDER BY s.created_at DESC LIMIT 5");
$recent_payments = $wpdb->get_results("SELECT p.*, s.first_name, s.last_name FROM {$pfx}esm_fee_payments p LEFT JOIN {$pfx}esm_students s ON s.id = p.student_id ORDER BY p.created_at DESC LIMIT 5");
$notices = $wpdb->get_results("SELECT * FROM {$pfx}esm_notices WHERE is_active=1 ORDER BY date_posted DESC LIMIT 5");

$role_welcome = [
    'esm_parent'   => "View your child's information.",
    'esm_student'  => 'View your academic information.',
    'esm_teacher'  => 'Manage your classes and academics.',
    'esm_accountant' => 'Financial overview at a glance.',
    'esm_bursar'   => 'Admissions and financial overview.',
];
?>
<div class="page-header">
    <div>
        <h1>Dashboard</h1>
        <p>Welcome back, <?php echo esc_html($user->display_name ?: $user->user_login); ?>! <?php echo esc_html($role_welcome[$role] ?? "Here's your school overview."); ?></p>
    </div>
    <div class="actions">
        <?php if (in_array($role, ['esm_super_admin', 'esm_accountant', 'esm_bursar', 'esm_teacher'], true)): ?>
        <a href="<?php echo esc_url(home_url('/sms/reports/')); ?>" class="btn btn-secondary"><i class="fas fa-chart-bar"></i> Reports</a>
        <?php endif; ?>
    </div>
</div>

<?php if ($role === 'esm_parent'): ?>
<div class="card" style="border-left:4px solid var(--primary);margin-bottom:16px;">
    <div class="card-body" style="display:flex;align-items:center;gap:16px;">
        <div style="width:48px;height:48px;background:var(--primary);color:#fff;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px;"><i class="fas fa-home"></i></div>
        <div style="flex:1;"><h3 style="margin:0;">Parent Portal</h3><p style="margin:0;color:var(--text-light);font-size:13px;">View your children's attendance, results, fees, and more.</p></div>
        <a href="<?php echo esc_url(home_url('/sms/parent-portal/')); ?>" class="btn btn-primary"><i class="fas fa-arrow-right"></i> Go to Portal</a>
    </div>
</div>
<?php elseif ($role === 'esm_student'): ?>
<div class="card" style="border-left:4px solid var(--primary);margin-bottom:16px;">
    <div class="card-body" style="display:flex;align-items:center;gap:16px;">
        <div style="width:48px;height:48px;background:var(--primary);color:#fff;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px;"><i class="fas fa-home"></i></div>
        <div style="flex:1;"><h3 style="margin:0;">Student Portal</h3><p style="margin:0;color:var(--text-light);font-size:13px;">View your results, attendance, fees, and timetable.</p></div>
        <a href="<?php echo esc_url(home_url('/sms/student-portal/')); ?>" class="btn btn-primary"><i class="fas fa-arrow-right"></i> Go to Portal</a>
    </div>
</div>
<?php endif; ?>

<div class="stats-grid">
    <?php if (in_array($role, ['esm_super_admin', 'esm_bursar'], true)): ?>
    <div class="stat-card"><div class="icon green"><i class="fas fa-user-graduate"></i></div><div class="info"><h3><?php echo esc_html($total_students); ?></h3><p>Total Students</p></div></div>
    <?php endif; ?>
    <?php if ($role === 'esm_super_admin'): ?>
    <div class="stat-card"><div class="icon blue"><i class="fas fa-chalkboard-teacher"></i></div><div class="info"><h3><?php echo esc_html($total_staff); ?></h3><p>Total Staff</p></div></div>
    <?php endif; ?>
    <?php if (in_array($role, ['esm_super_admin', 'esm_accountant', 'esm_bursar'], true)): ?>
    <div class="stat-card"><div class="icon yellow"><i class="fas fa-dollar-sign"></i></div><div class="info"><h3>$<?php echo esc_html(number_format($fees_month, 2)); ?></h3><p>Fees This Month</p></div></div>
    <?php endif; ?>
    <?php if ($role === 'esm_super_admin'): ?>
    <div class="stat-card"><div class="icon red"><i class="fas fa-sync-alt"></i></div><div class="info"><h3><?php echo esc_html($pending_sync); ?></h3><p>Pending Sync</p></div></div>
    <?php endif; ?>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
    <?php if (in_array($role, ['esm_super_admin', 'esm_bursar', 'esm_teacher'], true)): ?>
    <div class="card">
        <div class="card-header"><h3><i class="fas fa-user-graduate" style="color:var(--primary);margin-right:8px;"></i>Recent Students</h3><a href="<?php echo esc_url(home_url('/sms/students/')); ?>" class="btn btn-sm btn-secondary">View All</a></div>
        <div class="table-container">
            <table>
                <thead><tr><th>Adm No.</th><th>Name</th><th>Class</th><th>Status</th></tr></thead>
                <tbody>
                    <?php if ($recent_students): foreach ($recent_students as $s): ?>
                    <tr>
                        <td><?php echo esc_html($s->admission_number); ?></td>
                        <td><?php echo esc_html($s->first_name . ' ' . $s->last_name); ?></td>
                        <td><?php echo esc_html($s->class_name ?: '-'); ?></td>
                        <td><span class="badge badge-success"><?php echo esc_html($s->status); ?></span></td>
                    </tr>
                    <?php endforeach; else: ?>
                    <tr><td colspan="4" class="text-center" style="padding:20px;color:var(--text-light);">No students yet</td></tr>
                    <?php endif; ?>
                </tbody>
            </table>
        </div>
    </div>
    <?php endif; ?>

    <?php if (in_array($role, ['esm_super_admin', 'esm_accountant', 'esm_bursar'], true)): ?>
    <div class="card">
        <div class="card-header"><h3><i class="fas fa-dollar-sign" style="color:var(--secondary);margin-right:8px;"></i>Recent Payments</h3><a href="<?php echo esc_url(home_url('/sms/fees/')); ?>" class="btn btn-sm btn-secondary">View All</a></div>
        <div class="table-container">
            <table>
                <thead><tr><th>Receipt</th><th>Student</th><th>Amount</th><th>Date</th></tr></thead>
                <tbody>
                    <?php if ($recent_payments): foreach ($recent_payments as $p): ?>
                    <tr>
                        <td><?php echo esc_html($p->receipt_number); ?></td>
                        <td><?php echo esc_html($p->first_name . ' ' . $p->last_name); ?></td>
                        <td>$<?php echo esc_html(number_format($p->amount, 2)); ?></td>
                        <td><?php echo esc_html($p->payment_date); ?></td>
                    </tr>
                    <?php endforeach; else: ?>
                    <tr><td colspan="4" class="text-center" style="padding:20px;color:var(--text-light);">No payments yet</td></tr>
                    <?php endif; ?>
                </tbody>
            </table>
        </div>
    </div>
    <?php endif; ?>
</div>

<div class="card" style="margin-top:24px;">
    <div class="card-header"><h3><i class="fas fa-bullhorn" style="color:var(--accent);margin-right:8px;"></i>Recent Notices</h3><a href="<?php echo esc_url(home_url('/sms/communication/')); ?>" class="btn btn-sm btn-secondary">View All</a></div>
    <div class="card-body">
        <?php if ($notices): foreach ($notices as $n): ?>
        <div style="padding:12px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;">
            <div>
                <strong><?php echo esc_html($n->title); ?></strong>
                <span class="badge badge-info"><?php echo esc_html($n->category); ?></span>
                <p style="font-size:12px;color:var(--text-light);margin-top:4px;"><?php echo esc_html(mb_strimwidth(wp_strip_all_tags($n->content), 0, 100, '...')); ?></p>
            </div>
            <span style="font-size:11px;color:var(--text-light);white-space:nowrap;"><?php echo esc_html(mysql2date('M j, Y', $n->date_posted)); ?></span>
        </div>
        <?php endforeach; else: ?>
        <p class="text-center" style="padding:20px;color:var(--text-light);">No notices</p>
        <?php endif; ?>
    </div>
</div>
