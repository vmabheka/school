<?php
/**
 * Invoices — port of the offline app's templates/fees/invoices.html.
 * Reads the esm_invoices table which is new in this rebuild (the
 * previous plugin build had no invoice storage at all).
 */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;

$search = sanitize_text_field($_GET['search'] ?? '');
$status_f = sanitize_text_field($_GET['status'] ?? '');
$class_f = sanitize_text_field($_GET['class_id'] ?? '');

$where = ['1=1']; $params = [];
if ($search) {
    $where[] = "(i.invoice_number LIKE %s OR s.first_name LIKE %s OR s.last_name LIKE %s OR s.admission_number LIKE %s)";
    $like = '%' . $wpdb->esc_like($search) . '%';
    $params = array_merge($params, [$like, $like, $like, $like]);
}
if ($status_f) { $where[] = "i.status = %s"; $params[] = $status_f; }
if ($class_f) { $where[] = "s.class_id = %d"; $params[] = intval($class_f); }

$sql = "SELECT i.*, s.first_name, s.last_name, s.admission_number, c.name AS class_name
        FROM {$pfx}esm_invoices i
        LEFT JOIN {$pfx}esm_students s ON s.id = i.student_id
        LEFT JOIN {$pfx}esm_classes c ON c.id = s.class_id
        WHERE " . implode(' AND ', $where) . " ORDER BY i.issue_date DESC LIMIT 200";
$invoices = $params ? $wpdb->get_results($wpdb->prepare($sql, $params)) : $wpdb->get_results($sql);
$classes = $wpdb->get_results("SELECT id, name FROM {$pfx}esm_classes ORDER BY name");

$status_badge = ['Unpaid' => 'badge-danger', 'Partially Paid' => 'badge-warning', 'Paid' => 'badge-success', 'Cancelled' => 'badge-secondary'];
?>
<div class="page-header">
    <div><h1>Student Fee Invoices</h1><p>Manage and track fee invoices</p></div>
</div>

<div class="filter-bar" style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;align-items:center;">
    <form method="GET" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
        <input type="text" name="search" class="form-control" placeholder="Search invoice #, student name or adm..." value="<?php echo esc_attr($search); ?>" style="min-width:250px;">
        <select name="status" class="form-control">
            <option value="">All Statuses</option>
            <?php foreach (['Unpaid', 'Partially Paid', 'Paid', 'Cancelled'] as $s): ?>
            <option value="<?php echo esc_attr($s); ?>" <?php selected($status_f, $s); ?>><?php echo esc_html($s); ?></option>
            <?php endforeach; ?>
        </select>
        <select name="class_id" class="form-control">
            <option value="">All Classes</option>
            <?php foreach ($classes as $c): ?>
            <option value="<?php echo esc_attr($c->id); ?>" <?php selected($class_f, (string) $c->id); ?>><?php echo esc_html($c->name); ?></option>
            <?php endforeach; ?>
        </select>
        <button type="submit" class="btn btn-primary"><i class="fas fa-search"></i> Filter</button>
        <a href="<?php echo esc_url(home_url('/sms/invoices/')); ?>" class="btn btn-secondary">Reset</a>
    </form>
</div>

<div class="card">
    <div class="table-container">
        <table>
            <thead><tr><th>Invoice #</th><th>Student</th><th>Class</th><th>Issue Date</th><th>Subtotal</th><th>Discount</th><th>Total Billed</th><th>Status</th><th>PDF</th></tr></thead>
            <tbody>
                <?php if ($invoices): foreach ($invoices as $i): ?>
                <tr>
                    <td><strong><?php echo esc_html($i->invoice_number); ?></strong></td>
                    <td><?php echo esc_html($i->first_name . ' ' . $i->last_name); ?> <small style="color:var(--text-light);">(<?php echo esc_html($i->admission_number); ?>)</small></td>
                    <td><?php echo esc_html($i->class_name ?: '-'); ?></td>
                    <td><?php echo esc_html($i->issue_date); ?></td>
                    <td>$<?php echo esc_html(number_format($i->subtotal, 2)); ?></td>
                    <td>$<?php echo esc_html(number_format($i->discount_amount, 2)); ?></td>
                    <td><strong>$<?php echo esc_html(number_format($i->total_amount, 2)); ?></strong></td>
                    <td><span class="badge <?php echo esc_attr($status_badge[$i->status] ?? 'badge-secondary'); ?>"><?php echo esc_html($i->status); ?></span></td>
                    <td><a class="btn btn-sm btn-secondary" href="<?php echo esc_url(home_url('/sms/invoices/?pdf=' . $i->id)); ?>"><i class="fas fa-file-pdf"></i> Download</a></td>
                </tr>
                <?php endforeach; else: ?>
                <tr><td colspan="9" class="text-center" style="padding:30px;color:var(--text-light);">No invoices found</td></tr>
                <?php endif; ?>
            </tbody>
        </table>
    </div>
</div>
