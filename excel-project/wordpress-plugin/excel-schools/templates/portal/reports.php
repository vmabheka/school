<?php
/** Reports hub — port of the offline app's templates/reports/dashboard.html. */
if (!defined('ABSPATH')) exit;
?>
<div class="page-header">
    <div><h1>Reports &amp; Analytics</h1><p>Generate and view school reports</p></div>
    <div class="actions">
        <a class="btn btn-danger" href="<?php echo esc_url(home_url('/sms/reports/?pdf=all')); ?>"><i class="fas fa-file-pdf"></i> Download All PDF</a>
        <?php if ($role === 'esm_super_admin'): ?>
        <a class="btn btn-secondary" href="<?php echo esc_url(home_url('/sms/reports/?download=all')); ?>"><i class="fas fa-file-csv"></i> Download All CSV</a>
        <?php endif; ?>
    </div>
</div>

<div class="stats-grid">
    <a href="<?php echo esc_url(home_url('/sms/reports/?type=students')); ?>" class="stat-card" style="text-decoration:none;color:inherit;">
        <div class="icon green"><i class="fas fa-user-graduate"></i></div>
        <div class="info"><h3>Student</h3><p>Enrollment reports</p></div>
    </a>
    <a href="<?php echo esc_url(home_url('/sms/reports/?type=fees')); ?>" class="stat-card" style="text-decoration:none;color:inherit;">
        <div class="icon yellow"><i class="fas fa-dollar-sign"></i></div>
        <div class="info"><h3>Fee</h3><p>Payment reports</p></div>
    </a>
    <a href="<?php echo esc_url(home_url('/sms/reports/?type=exams')); ?>" class="stat-card" style="text-decoration:none;color:inherit;">
        <div class="icon purple"><i class="fas fa-file-alt"></i></div>
        <div class="info"><h3>Exam</h3><p>Results reports</p></div>
    </a>
</div>

<div class="card" style="margin-bottom:20px;">
    <div class="card-body" style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
        <strong>PDF Downloads:</strong>
        <a class="btn btn-secondary" href="<?php echo esc_url(home_url('/sms/reports/?pdf=students')); ?>"><i class="fas fa-file-pdf"></i> Student Report</a>
        <a class="btn btn-secondary" href="<?php echo esc_url(home_url('/sms/reports/?pdf=fees')); ?>"><i class="fas fa-file-pdf"></i> Fee Report</a>
        <a class="btn btn-secondary" href="<?php echo esc_url(home_url('/sms/reports/?pdf=exams')); ?>"><i class="fas fa-file-pdf"></i> Exam Report</a>
    </div>
</div>

<?php
global $wpdb;
$pfx = $wpdb->prefix;
$type = sanitize_text_field($_GET['type'] ?? '');
if ($type === 'students'):
    $by_class = $wpdb->get_results("SELECT c.name, COUNT(s.id) AS cnt FROM {$pfx}esm_classes c LEFT JOIN {$pfx}esm_students s ON s.class_id = c.id AND s.status='Active' GROUP BY c.id ORDER BY c.name");
?>
<div class="card" style="margin-top:20px;">
    <div class="card-header"><h3>Students by Class</h3></div>
    <div class="table-container"><table><thead><tr><th>Class</th><th>Active Students</th></tr></thead><tbody>
        <?php foreach ($by_class as $r): ?>
        <tr><td><?php echo esc_html($r->name); ?></td><td><?php echo esc_html($r->cnt); ?></td></tr>
        <?php endforeach; ?>
    </tbody></table></div>
</div>
<?php elseif ($type === 'fees'):
    $by_month = $wpdb->get_results("SELECT DATE_FORMAT(payment_date, '%Y-%m') AS ym, SUM(amount) AS total FROM {$pfx}esm_fee_payments GROUP BY ym ORDER BY ym DESC LIMIT 12");
?>
<div class="card" style="margin-top:20px;">
    <div class="card-header"><h3>Fee Collection by Month</h3></div>
    <div class="table-container"><table><thead><tr><th>Month</th><th>Collected</th></tr></thead><tbody>
        <?php foreach ($by_month as $r): ?>
        <tr><td><?php echo esc_html($r->ym); ?></td><td>$<?php echo esc_html(number_format($r->total, 2)); ?></td></tr>
        <?php endforeach; ?>
    </tbody></table></div>
</div>
<?php elseif ($type === 'exams'):
    $results = $wpdb->get_results("SELECT e.name AS exam_name, COUNT(r.id) AS cnt, AVG(r.marks_obtained) AS avg_mark FROM {$pfx}esm_exams e LEFT JOIN {$pfx}esm_exam_results r ON r.exam_id = e.id GROUP BY e.id ORDER BY e.start_date DESC");
?>
<div class="card" style="margin-top:20px;">
    <div class="card-header"><h3>Exam Results Summary</h3></div>
    <div class="table-container"><table><thead><tr><th>Exam</th><th>Results Recorded</th><th>Average Mark</th></tr></thead><tbody>
        <?php foreach ($results as $r): ?>
        <tr><td><?php echo esc_html($r->exam_name); ?></td><td><?php echo esc_html($r->cnt); ?></td><td><?php echo esc_html($r->avg_mark !== null ? number_format($r->avg_mark, 1) : '-'); ?></td></tr>
        <?php endforeach; ?>
    </tbody></table></div>
</div>
<?php endif; ?>
