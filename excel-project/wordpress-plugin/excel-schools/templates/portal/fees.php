<?php
/**
 * Fee & Invoice Management dashboard — port of the offline app's
 * templates/fees/dashboard.html stat cards, computed from the current
 * term/academic year's invoices and payments (mirrors app.py fees_dashboard()).
 */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;

$ay = $wpdb->get_row("SELECT * FROM {$pfx}esm_academic_years WHERE is_current=1 LIMIT 1");
$term = $wpdb->get_row("SELECT * FROM {$pfx}esm_terms WHERE is_current=1 LIMIT 1");

$invoices_count = 0; $invoiced_subtotal = 0; $invoiced_discount = 0; $invoiced_net = 0;
$total_collected = 0; $uninvoiced_count = 0;

if ($ay && $term) {
    $inv_row = $wpdb->get_row($wpdb->prepare(
        "SELECT COUNT(*) AS cnt, COALESCE(SUM(subtotal),0) AS sub, COALESCE(SUM(discount_amount),0) AS disc, COALESCE(SUM(total_amount),0) AS net
         FROM {$pfx}esm_invoices WHERE academic_year_id=%d AND term_id=%d", $ay->id, $term->id));
    $invoices_count = (int) $inv_row->cnt; $invoiced_subtotal = (float) $inv_row->sub;
    $invoiced_discount = (float) $inv_row->disc; $invoiced_net = (float) $inv_row->net;

    $total_collected = (float) $wpdb->get_var($wpdb->prepare(
        "SELECT COALESCE(SUM(amount),0) FROM {$pfx}esm_fee_payments WHERE academic_year_id=%d AND term_id=%d", $ay->id, $term->id));

    $active_students = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_students WHERE status='Active'");
    $invoiced_students = (int) $wpdb->get_var($wpdb->prepare(
        "SELECT COUNT(DISTINCT student_id) FROM {$pfx}esm_invoices WHERE academic_year_id=%d AND term_id=%d", $ay->id, $term->id));
    $uninvoiced_count = max(0, $active_students - $invoiced_students);
}
$outstanding = max(0, $invoiced_net - $total_collected);
?>
<div class="page-header">
    <div><h1>Fee &amp; Invoice Management</h1><p>Manage billing invoices, fee structures, payments, and balances</p></div>
    <div class="actions">
        <a href="<?php echo esc_url(home_url('/sms/invoices/')); ?>" class="btn btn-secondary"><i class="fas fa-file-invoice-dollar"></i> Invoices</a>
    </div>
</div>

<?php if ($uninvoiced_count > 0): ?>
<div style="background:#fffbeb;border:1px solid #fde68a;padding:12px 18px;border-radius:8px;margin-bottom:16px;">
    <i class="fas fa-exclamation-triangle" style="color:#d97706;margin-right:8px;"></i>
    <strong>Uninvoiced Students Detected:</strong> There are <strong><?php echo esc_html($uninvoiced_count); ?></strong> active students without generated invoices for <?php echo esc_html(($ay->name ?? '') . ' ' . ($term->name ?? '')); ?>.
</div>
<?php endif; ?>

<div class="stats-grid">
    <div class="stat-card"><div class="icon green"><i class="fas fa-file-invoice"></i></div><div class="info"><h3>$<?php echo esc_html(number_format($invoiced_net, 2)); ?></h3><p>Total Billed (<?php echo esc_html($invoices_count); ?> Invoices)</p></div></div>
    <div class="stat-card"><div class="icon yellow"><i class="fas fa-coins"></i></div><div class="info"><h3>$<?php echo esc_html(number_format($total_collected, 2)); ?></h3><p>Collected Payments</p></div></div>
    <div class="stat-card"><div class="icon red"><i class="fas fa-exclamation-circle"></i></div><div class="info"><h3>$<?php echo esc_html(number_format($outstanding, 2)); ?></h3><p>Billed Outstanding</p></div></div>
    <div class="stat-card"><div class="icon purple"><i class="fas fa-award"></i></div><div class="info"><h3>$<?php echo esc_html(number_format($invoiced_discount, 2)); ?></h3><p>Scholarship Discounts</p></div></div>
</div>

<div class="card">
    <div class="card-header"><h3>Recent Fee Payments</h3><a href="<?php echo esc_url(home_url('/sms/invoices/')); ?>" class="btn btn-sm btn-secondary">View Invoices</a></div>
    <div class="table-container">
        <table>
            <thead><tr><th>Receipt</th><th>Student</th><th>Amount</th><th>Method</th><th>Date</th></tr></thead>
            <tbody>
                <?php
                $payments = $wpdb->get_results("SELECT p.*, s.first_name, s.last_name FROM {$pfx}esm_fee_payments p LEFT JOIN {$pfx}esm_students s ON s.id = p.student_id ORDER BY p.created_at DESC LIMIT 25");
                if ($payments): foreach ($payments as $p): ?>
                <tr>
                    <td><?php echo esc_html($p->receipt_number); ?></td>
                    <td><?php echo esc_html($p->first_name . ' ' . $p->last_name); ?></td>
                    <td>$<?php echo esc_html(number_format($p->amount, 2)); ?></td>
                    <td><?php echo esc_html($p->payment_method ?: '-'); ?></td>
                    <td><?php echo esc_html($p->payment_date); ?></td>
                </tr>
                <?php endforeach; else: ?>
                <tr><td colspan="5" class="text-center" style="padding:30px;color:var(--text-light);">No payments recorded</td></tr>
                <?php endif; ?>
            </tbody>
        </table>
    </div>
</div>
