<?php
/**
 * Parent Portal — port of the offline app's templates/dashboard/parent_portal.html,
 * showing each linked child's class, scholarship label, and fee balance.
 */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;

$parent = $parent_id ? $wpdb->get_row($wpdb->prepare("SELECT * FROM {$pfx}esm_parents WHERE id=%d", $parent_id)) : null;
$children = [];
if ($parent_id) {
    $children = $wpdb->get_results($wpdb->prepare(
        "SELECT s.*, c.name AS class_name FROM {$pfx}esm_students s
         INNER JOIN {$pfx}esm_student_parent sp ON sp.student_id = s.id
         LEFT JOIN {$pfx}esm_classes c ON c.id = s.class_id
         WHERE sp.parent_id = %d", $parent_id));
}
?>
<div class="page-header">
    <div><h1><i class="fas fa-user-friends" style="color:var(--primary);"></i> Parent Portal</h1>
    <p>Welcome, <?php echo esc_html($parent ? ($parent->first_name . ' ' . $parent->last_name) : $user->display_name); ?></p></div>
</div>

<?php if ($children): foreach ($children as $child):
    $total_due = (float) $wpdb->get_var($wpdb->prepare("SELECT COALESCE(SUM(total_amount),0) FROM {$pfx}esm_invoices WHERE student_id=%d", $child->id));
    $paid = (float) $wpdb->get_var($wpdb->prepare("SELECT COALESCE(SUM(amount),0) FROM {$pfx}esm_fee_payments WHERE student_id=%d", $child->id));
    $balance = $total_due - $paid;
?>
<div class="card" style="margin-bottom:24px;">
    <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
        <h3><i class="fas fa-user-graduate" style="color:var(--primary);margin-right:8px;"></i><?php echo esc_html($child->first_name . ' ' . $child->last_name); ?></h3>
        <div><span class="badge badge-info"><?php echo esc_html($child->admission_number); ?></span> <span class="badge badge-success"><?php echo esc_html($child->status); ?></span></div>
    </div>
    <div class="card-body">
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:20px;">
            <div style="padding:12px;background:var(--bg);border-radius:8px;text-align:center;"><div style="font-size:12px;color:var(--text-light);">Class</div><div style="font-size:16px;font-weight:700;color:var(--primary);"><?php echo esc_html($child->class_name ?: 'N/A'); ?></div></div>
            <div style="padding:12px;background:var(--bg);border-radius:8px;text-align:center;"><div style="font-size:12px;color:var(--text-light);">Fee Classification</div><div style="font-size:16px;font-weight:700;color:var(--secondary);"><?php echo esc_html($child->fee_classification); ?></div></div>
            <div style="padding:12px;background:var(--bg);border-radius:8px;text-align:center;"><div style="font-size:12px;color:var(--text-light);">Fee Balance</div><div style="font-size:16px;font-weight:700;color:<?php echo $balance > 0 ? 'var(--accent)' : '#10b981'; ?>;">$<?php echo esc_html(number_format($balance, 2)); ?></div></div>
        </div>
        <div class="card" style="border:1px solid var(--border);">
            <div class="card-header" style="padding:10px 16px;"><h4 style="margin:0;font-size:14px;">Fee Details</h4></div>
            <div class="card-body" style="padding:12px 16px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:8px;"><span>Total Billed:</span><strong>$<?php echo esc_html(number_format($total_due, 2)); ?></strong></div>
                <div style="display:flex;justify-content:space-between;margin-bottom:8px;color:#10b981;"><span>Total Paid:</span><strong>$<?php echo esc_html(number_format($paid, 2)); ?></strong></div>
                <hr style="border:none;border-top:1px solid var(--border);margin:8px 0;">
                <div style="display:flex;justify-content:space-between;font-size:16px;"><span><strong>Balance:</strong></span><strong style="color:<?php echo $balance > 0 ? 'var(--accent)' : '#10b981'; ?>;">$<?php echo esc_html(number_format($balance, 2)); ?></strong></div>
            </div>
        </div>
    </div>
</div>
<?php endforeach; else: ?>
<div class="card"><div class="card-body empty-state"><i class="fas fa-user-friends"></i><h3>No linked children found</h3><p>Contact the school office to link your account to your child's record.</p></div></div>
<?php endif; ?>
