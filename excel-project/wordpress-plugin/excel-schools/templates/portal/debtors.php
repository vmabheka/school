<?php
/**
 * Debtors — students with outstanding fee balances, computed the same
 * way as the offline app's debtors_list(): net invoiced total minus
 * total payments made, per student.
 */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;

$class_filter = absint($_GET['class_id'] ?? 0);
$grade_level_filter = sanitize_text_field($_GET['grade_level'] ?? '');
$school_filter = sanitize_key($_GET['school'] ?? '');
if (!in_array($school_filter, ['', 'primary', 'secondary'], true)) $school_filter = '';
$classes = $wpdb->get_results("SELECT id, name, level FROM {$pfx}esm_classes ORDER BY name");
$grade_levels = $wpdb->get_col("SELECT DISTINCT level FROM {$pfx}esm_classes WHERE level IS NOT NULL AND level<>'' ORDER BY level");

$rows = $wpdb->get_results("
    SELECT s.id, s.admission_number, s.first_name, s.last_name, s.class_id,
           c.name AS class_name, c.level AS grade_level,
           COALESCE(inv.net, 0) AS net_due, COALESCE(pay.paid, 0) AS paid
    FROM {$pfx}esm_students s
    LEFT JOIN {$pfx}esm_classes c ON c.id = s.class_id
    LEFT JOIN (SELECT student_id, SUM(total_amount) AS net FROM {$pfx}esm_invoices GROUP BY student_id) inv ON inv.student_id = s.id
    LEFT JOIN (SELECT student_id, SUM(amount) AS paid FROM {$pfx}esm_fee_payments GROUP BY student_id) pay ON pay.student_id = s.id
    WHERE s.status = 'Active'
");

$debtors = [];
foreach ($rows as $r) {
    if ($class_filter && (int) $r->class_id !== $class_filter) continue;
    if ($grade_level_filter !== '' && $r->grade_level !== $grade_level_filter) continue;
    $is_primary = ESM_Helpers::is_primary_level($r->grade_level);
    if ($school_filter === 'primary' && !$is_primary) continue;
    if ($school_filter === 'secondary' && $is_primary) continue;

    $balance = (float) $r->net_due - (float) $r->paid;
    if ($balance > 0.01) {
        $debtors[] = [
            'name' => $r->first_name . ' ' . $r->last_name,
            'adm' => $r->admission_number,
            'class' => $r->class_name,
            'grade_level' => $r->grade_level,
            'school' => $is_primary ? 'Primary' : 'Secondary',
            'net_due' => (float) $r->net_due,
            'paid' => (float) $r->paid,
            'balance' => $balance,
        ];
    }
}
usort($debtors, function ($a, $b) { return $b['balance'] <=> $a['balance']; });

$total_owed = array_sum(array_column($debtors, 'balance'));
$total_debtors = count($debtors);
?>
<div class="page-header">
    <div><h1>Debtors</h1><p>Students with outstanding fee balances</p></div>
</div>

<div class="card" style="margin-bottom:20px;">
    <div class="card-body">
        <form method="get" class="filter-bar" style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
            <select name="class_id" class="form-control">
                <option value="">All Classes</option>
                <?php foreach ($classes as $class): ?>
                <option value="<?php echo esc_attr($class->id); ?>" <?php selected($class_filter, $class->id); ?>><?php echo esc_html($class->name); ?></option>
                <?php endforeach; ?>
            </select>
            <select name="grade_level" class="form-control">
                <option value="">All Grades / Levels</option>
                <?php foreach ($grade_levels as $grade_level): ?>
                <option value="<?php echo esc_attr($grade_level); ?>" <?php selected($grade_level_filter, $grade_level); ?>><?php echo esc_html($grade_level); ?></option>
                <?php endforeach; ?>
            </select>
            <select name="school" class="form-control">
                <option value="">All Schools</option>
                <option value="primary" <?php selected($school_filter, 'primary'); ?>>Primary School</option>
                <option value="secondary" <?php selected($school_filter, 'secondary'); ?>>Secondary School</option>
            </select>
            <button class="btn btn-primary" type="submit"><i class="fas fa-filter"></i> Apply Filters</button>
            <?php if ($class_filter || $grade_level_filter || $school_filter): ?>
            <a class="btn btn-secondary" href="<?php echo esc_url(home_url('/sms/debtors/')); ?>"><i class="fas fa-times"></i> Reset</a>
            <?php endif; ?>
        </form>
    </div>
</div>

<div class="stats-grid">
    <div class="stat-card"><div class="icon red"><i class="fas fa-exclamation-triangle"></i></div><div class="info"><h3><?php echo esc_html($total_debtors); ?></h3><p>Students Owing</p></div></div>
    <div class="stat-card"><div class="icon yellow"><i class="fas fa-dollar-sign"></i></div><div class="info"><h3>$<?php echo esc_html(number_format($total_owed, 2)); ?></h3><p>Total Outstanding</p></div></div>
</div>

<div class="card">
    <div class="table-container">
        <table>
            <thead><tr><th>Adm No.</th><th>Student</th><th>Class</th><th>Net Due</th><th>Paid</th><th>Balance</th></tr></thead>
            <tbody>
                <?php if ($debtors): foreach ($debtors as $d): ?>
                <tr>
                    <td><?php echo esc_html($d['adm']); ?></td>
                    <td><?php echo esc_html($d['name']); ?></td>
                    <td>
                        <?php echo esc_html($d['class'] ?: '-'); ?>
                        <?php if ($d['grade_level']): ?><br><small style="color:var(--text-light);"><?php echo esc_html($d['grade_level'] . ' · ' . $d['school'] . ' School'); ?></small><?php endif; ?>
                    </td>
                    <td>$<?php echo esc_html(number_format($d['net_due'], 2)); ?></td>
                    <td>$<?php echo esc_html(number_format($d['paid'], 2)); ?></td>
                    <td><strong style="color:var(--danger);">$<?php echo esc_html(number_format($d['balance'], 2)); ?></strong></td>
                </tr>
                <?php endforeach; else: ?>
                <tr><td colspan="6" class="text-center" style="padding:30px;color:var(--text-light);">No outstanding balances — great job!</td></tr>
                <?php endif; ?>
            </tbody>
        </table>
    </div>
</div>
