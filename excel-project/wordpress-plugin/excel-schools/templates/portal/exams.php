<?php
/** Exams — port of the offline app's templates/exams/list.html. */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;
$exams = $wpdb->get_results("SELECT e.*, t.name AS term_name FROM {$pfx}esm_exams e LEFT JOIN {$pfx}esm_terms t ON t.id = e.term_id ORDER BY e.start_date DESC");
?>
<div class="page-header">
    <div><h1>Exams &amp; Results</h1><p>Manage examinations and student results</p></div>
</div>
<div class="card">
    <div class="table-container">
        <table>
            <thead><tr><th>Exam Name</th><th>Type</th><th>Term</th><th>Start Date</th><th>End Date</th></tr></thead>
            <tbody>
                <?php if ($exams): foreach ($exams as $e): ?>
                <tr>
                    <td><strong><?php echo esc_html($e->name); ?></strong></td>
                    <td><span class="badge badge-info"><?php echo esc_html($e->exam_type ?: '-'); ?></span></td>
                    <td><?php echo esc_html($e->term_name ?: '-'); ?></td>
                    <td><?php echo esc_html($e->start_date ?: '-'); ?></td>
                    <td><?php echo esc_html($e->end_date ?: '-'); ?></td>
                </tr>
                <?php endforeach; else: ?>
                <tr><td colspan="5" class="text-center" style="padding:40px;color:var(--text-light);"><i class="fas fa-file-alt" style="font-size:32px;opacity:.3;display:block;margin-bottom:8px;"></i>No exams yet</td></tr>
                <?php endif; ?>
            </tbody>
        </table>
    </div>
</div>
