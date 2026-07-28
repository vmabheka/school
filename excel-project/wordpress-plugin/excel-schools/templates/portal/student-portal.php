<?php
/** Student Portal — port of the offline app's templates/dashboard/student_portal.html. */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;

$student = $student_id ? $wpdb->get_row($wpdb->prepare(
    "SELECT s.*, c.name AS class_name FROM {$pfx}esm_students s LEFT JOIN {$pfx}esm_classes c ON c.id = s.class_id WHERE s.id=%d", $student_id)) : null;

$total_due = 0; $paid = 0; $results_count = 0;
if ($student) {
    $total_due = (float) $wpdb->get_var($wpdb->prepare("SELECT COALESCE(SUM(total_amount),0) FROM {$pfx}esm_invoices WHERE student_id=%d", $student->id));
    $paid = (float) $wpdb->get_var($wpdb->prepare("SELECT COALESCE(SUM(amount),0) FROM {$pfx}esm_fee_payments WHERE student_id=%d", $student->id));
    $results_count = (int) $wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM {$pfx}esm_exam_results WHERE student_id=%d", $student->id));
}
$balance = $total_due - $paid;
?>
<div class="page-header"><div><h1><i class="fas fa-user-graduate" style="color:var(--primary);"></i> Student Portal</h1><p>Welcome, <?php echo esc_html($student ? ($student->first_name . ' ' . $student->last_name) : $user->display_name); ?></p></div></div>

<?php if ($student): ?>
<div class="card" style="margin-bottom:24px;background:linear-gradient(135deg,var(--primary),var(--primary-light));color:#fff;">
    <div class="card-body" style="display:flex;align-items:center;gap:20px;">
        <div style="width:80px;height:80px;background:rgba(255,255,255,.2);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:700;"><?php echo esc_html(strtoupper(substr($student->first_name, 0, 1) . substr($student->last_name, 0, 1))); ?></div>
        <div>
            <h2 style="color:#fff;"><?php echo esc_html($student->first_name . ' ' . $student->last_name); ?></h2>
            <p style="opacity:.85;">Adm #<?php echo esc_html($student->admission_number); ?> | <?php echo esc_html($student->class_name ?: 'No Class'); ?> | <?php echo esc_html($student->fee_classification); ?></p>
        </div>
    </div>
</div>

<div class="stats-grid">
    <div class="stat-card"><div class="icon green"><i class="fas fa-dollar-sign"></i></div><div class="info"><h3>$<?php echo esc_html(number_format($paid, 2)); ?></h3><p>Total Paid</p></div></div>
    <div class="stat-card"><div class="icon <?php echo $balance > 0 ? 'red' : 'green'; ?>"><i class="fas fa-balance-scale"></i></div><div class="info"><h3>$<?php echo esc_html(number_format($balance, 2)); ?></h3><p>Outstanding Balance</p></div></div>
    <div class="stat-card"><div class="icon blue"><i class="fas fa-chart-line"></i></div><div class="info"><h3><?php echo esc_html($results_count); ?></h3><p>Exam Results</p></div></div>
</div>

<div class="card">
    <div class="card-header"><h3>Recent Exam Results</h3></div>
    <div class="table-container">
        <table>
            <thead><tr><th>Exam</th><th>Subject</th><th>Marks</th><th>Grade</th></tr></thead>
            <tbody>
                <?php
                $results = $wpdb->get_results($wpdb->prepare(
                    "SELECT r.*, e.name AS exam_name, sub.name AS subject_name FROM {$pfx}esm_exam_results r
                     LEFT JOIN {$pfx}esm_exams e ON e.id = r.exam_id LEFT JOIN {$pfx}esm_subjects sub ON sub.id = r.subject_id
                     WHERE r.student_id=%d ORDER BY r.id DESC LIMIT 20", $student->id));
                if ($results): foreach ($results as $r): ?>
                <tr>
                    <td><?php echo esc_html($r->exam_name); ?></td>
                    <td><?php echo esc_html($r->subject_name); ?></td>
                    <td><?php echo esc_html($r->marks_obtained); ?> / <?php echo esc_html($r->marks_total); ?></td>
                    <td><span class="badge badge-info"><?php echo esc_html($r->grade ?: '-'); ?></span></td>
                </tr>
                <?php endforeach; else: ?>
                <tr><td colspan="4" class="text-center" style="padding:20px;color:var(--text-light);">No results recorded yet</td></tr>
                <?php endif; ?>
            </tbody>
        </table>
    </div>
</div>
<?php else: ?>
<div class="card"><div class="card-body empty-state"><i class="fas fa-user-graduate"></i><h3>No student record linked to this account</h3></div></div>
<?php endif; ?>
