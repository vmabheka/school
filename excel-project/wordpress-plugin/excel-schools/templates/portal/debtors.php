<?php
/**
 * Debtors — students with outstanding fee balances, computed the same
 * way as the offline app's debtors_list(): net invoiced total minus
 * total payments made, per student.
 */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;

$rows = $wpdb->get_results("
    SELECT s.id, s.admission_number, s.first_name, s.last_name, c.name AS class_name,
           COALESCE(inv.net, 0) AS net_due, COALESCE(pay.paid, 0) AS paid
    FROM {$pfx}esm_students s
    LEFT JOIN {$pfx}esm_classes c ON c.id = s.class_id
    LEFT JOIN (SELECT student_id, SUM(total_amount) AS net FROM {$pfx}esm_invoices GROUP BY student_id) inv ON inv.student_id = s.id
    LEFT JOIN (SELECT student_id, SUM(amount) AS paid FROM {$pfx}esm_fee_payments GROUP BY student_id) pay ON pay.student_id = s.id
    WHERE s.status = 'Active'
");

$debtors = [];
foreach ($rows as $r) {
    $balance = (float) $r->net_due - (float) $r->paid;
    if ($balance > 0.01) {
        $debtors[] = ['name' => $r->first_name . ' ' . $r->last_name, 'adm' => $r->admission_number, 'class' => $r->class_name, 'net_due' => (float) $r->net_due, 'paid' => (float) $r->paid, 'balance' => $balance];
    }
}
usort($debtors, function ($a, $b) { return $b['balance'] <=> $a['balance']; });

$total_owed = array_sum(array_column($debtors, 'balance'));
$total_debtors = count($debtors);
?>
<div class="page-header">
    <div><h1>Debtors</h1><p>Students with outstanding fee balances</p></div>
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
                    <td><?php echo esc_html($d['class'] ?: '-'); ?></td>
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
