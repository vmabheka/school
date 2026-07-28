<?php
/**
 * Students list — direct port of the offline app's templates/students/list.html
 * (same filters, same columns, same badge logic for fee_classification/status).
 */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;

$search   = sanitize_text_field($_GET['search'] ?? '');
$class_f  = sanitize_text_field($_GET['class'] ?? '');
$status_f = sanitize_text_field($_GET['status'] ?? '');
$sch_f    = sanitize_text_field($_GET['scholarship'] ?? '');

$where = ['1=1'];
$params = [];
if ($search) {
    $where[] = "(s.admission_number LIKE %s OR s.first_name LIKE %s OR s.last_name LIKE %s)";
    $like = '%' . $wpdb->esc_like($search) . '%';
    $params = array_merge($params, [$like, $like, $like]);
}
if ($class_f) { $where[] = "s.class_id = %d"; $params[] = intval($class_f); }
if ($status_f) { $where[] = "s.status = %s"; $params[] = $status_f; }
if ($sch_f === 'Any Scholarship') {
    $where[] = "s.fee_classification != 'Regular'";
} elseif ($sch_f) {
    $where[] = "s.fee_classification = %s"; $params[] = $sch_f;
}

$sql = "SELECT s.*, c.name AS class_name FROM {$pfx}esm_students s LEFT JOIN {$pfx}esm_classes c ON c.id = s.class_id WHERE " . implode(' AND ', $where) . " ORDER BY s.last_name ASC LIMIT 200";
$students = $params ? $wpdb->get_results($wpdb->prepare($sql, $params)) : $wpdb->get_results($sql);
$classes = $wpdb->get_results("SELECT id, name FROM {$pfx}esm_classes ORDER BY name");

$badge_map = [
    'Regular' => 'badge-secondary', 'Staff Scholarship' => 'badge-info',
    'Academic Scholarship' => 'badge-primary', 'Sports Scholarship' => 'badge-warning',
    'Bursary' => 'badge-success', 'Orphan' => 'badge-danger',
];
$status_badge = ['Active' => 'badge-success', 'Inactive' => 'badge-danger'];
?>
<div class="page-header">
    <div><h1>Students</h1><p>Manage student enrollment and records</p></div>
    <div class="actions">
        <?php if (in_array($role, ['esm_super_admin', 'esm_bursar'], true)): ?>
        <a href="<?php echo esc_url(home_url('/sms/students/?action=add')); ?>" class="btn btn-primary"><i class="fas fa-plus"></i> Add Student</a>
        <?php endif; ?>
    </div>
</div>

<div class="filter-bar" style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;align-items:center;">
    <form method="GET" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
        <input type="text" name="search" class="form-control" placeholder="Search by name or admission no." value="<?php echo esc_attr($search); ?>" style="min-width:250px;">
        <select name="class" class="form-control">
            <option value="">All Classes</option>
            <?php foreach ($classes as $c): ?>
            <option value="<?php echo esc_attr($c->id); ?>" <?php selected($class_f, (string) $c->id); ?>><?php echo esc_html($c->name); ?></option>
            <?php endforeach; ?>
        </select>
        <select name="status" class="form-control">
            <option value="">All Status</option>
            <?php foreach (['Active', 'Inactive', 'Graduated', 'Transferred'] as $s): ?>
            <option value="<?php echo esc_attr($s); ?>" <?php selected($status_f, $s); ?>><?php echo esc_html($s); ?></option>
            <?php endforeach; ?>
        </select>
        <select name="scholarship" class="form-control">
            <option value="">All Classifications</option>
            <?php foreach (['Regular', 'Any Scholarship', 'Staff Scholarship', 'Academic Scholarship', 'Sports Scholarship', 'Bursary', 'Orphan'] as $s): ?>
            <option value="<?php echo esc_attr($s); ?>" <?php selected($sch_f, $s); ?>><?php echo esc_html($s); ?></option>
            <?php endforeach; ?>
        </select>
        <button type="submit" class="btn btn-primary"><i class="fas fa-search"></i> Search</button>
        <a href="<?php echo esc_url(home_url('/sms/students/')); ?>" class="btn btn-secondary"><i class="fas fa-times"></i> Clear</a>
    </form>
</div>

<div class="card">
    <div class="table-container">
        <table>
            <thead><tr><th>Adm No.</th><th>Name</th><th>Gender</th><th>Class</th><th>Fee Classification</th><th>Status</th></tr></thead>
            <tbody>
                <?php if ($students): foreach ($students as $s): ?>
                <tr>
                    <td><strong><?php echo esc_html($s->admission_number); ?></strong></td>
                    <td><?php echo esc_html(trim($s->first_name . ' ' . $s->other_names . ' ' . $s->last_name)); ?></td>
                    <td><?php echo esc_html($s->gender ?: '-'); ?></td>
                    <td><?php echo esc_html($s->class_name ?: '-'); ?></td>
                    <td>
                        <span class="badge <?php echo esc_attr($badge_map[$s->fee_classification] ?? 'badge-secondary'); ?>"><?php echo esc_html($s->fee_classification ?: 'Regular'); ?></span>
                        <?php if ($s->scholarship_type === 'Full'): ?><span class="badge badge-success" style="font-size:10px;">100%</span>
                        <?php elseif ($s->scholarship_type === 'Partial'): ?><span class="badge badge-warning" style="font-size:10px;"><?php echo esc_html(round($s->scholarship_percentage)); ?>%</span>
                        <?php endif; ?>
                    </td>
                    <td><span class="badge <?php echo esc_attr($status_badge[$s->status] ?? 'badge-info'); ?>"><?php echo esc_html($s->status); ?></span></td>
                </tr>
                <?php endforeach; else: ?>
                <tr><td colspan="6" class="text-center" style="padding:30px;color:var(--text-light);">No students found</td></tr>
                <?php endif; ?>
            </tbody>
        </table>
    </div>
</div>
