<?php
/** Class management for super admins and bursars. */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;
$classes = $wpdb->get_results("SELECT c.*, ay.name AS academic_year, CONCAT(s.first_name,' ',s.last_name) AS teacher_name, COUNT(st.id) AS student_count FROM {$pfx}esm_classes c LEFT JOIN {$pfx}esm_academic_years ay ON ay.id=c.academic_year_id LEFT JOIN {$pfx}esm_staff s ON s.id=c.teacher_id LEFT JOIN {$pfx}esm_students st ON st.class_id=c.id AND st.status='Active' GROUP BY c.id ORDER BY c.level,c.name");
$years = $wpdb->get_results("SELECT id,name,is_current FROM {$pfx}esm_academic_years ORDER BY start_date DESC");
$teachers = $wpdb->get_results("SELECT id,first_name,last_name FROM {$pfx}esm_staff WHERE status='Active' ORDER BY last_name,first_name");
?>
<div class="page-header">
    <div><h1><i class="fas fa-school" style="color:var(--primary)"></i> Classes</h1><p>Create classes for student admissions. Changes are queued for manual and automatic sync.</p></div>
</div>

<?php if (isset($_GET['class_created'])): ?>
<div class="card" style="border-left:4px solid var(--success);margin-bottom:16px"><div class="card-body">Class created and queued for synchronization.</div></div>
<?php elseif (isset($_GET['class_error'])): ?>
<div class="card" style="border-left:4px solid var(--danger);margin-bottom:16px"><div class="card-body">
<?php echo $_GET['class_error'] === 'duplicate' ? 'That class already exists for the selected academic year.' : 'The class could not be created. Check the required fields and try again.'; ?>
</div></div>
<?php endif; ?>

<div class="card" style="margin-bottom:20px">
    <div class="card-header"><h3><i class="fas fa-plus"></i> Add Class</h3></div>
    <div class="card-body">
        <form method="post">
            <?php wp_nonce_field('esm_create_class', 'esm_class_nonce'); ?>
            <div class="form-grid">
                <div class="form-group"><label>Level *</label><input class="form-control" name="level" required placeholder="e.g. Grade 5 or Form 3"></div>
                <div class="form-group"><label>Stream</label><input class="form-control" name="stream" placeholder="e.g. A, Blue or Sciences"></div>
                <div class="form-group"><label>Class Name</label><input class="form-control" name="name" placeholder="Generated if blank"></div>
                <div class="form-group"><label>Capacity</label><input class="form-control" type="number" min="1" name="capacity" value="40" required></div>
                <div class="form-group"><label>Academic Year</label><select class="form-control" name="academic_year_id"><option value="">Not assigned</option><?php foreach ($years as $year): ?><option value="<?php echo esc_attr($year->id); ?>" <?php selected($year->is_current, 1); ?>><?php echo esc_html($year->name . ($year->is_current ? ' (Current)' : '')); ?></option><?php endforeach; ?></select></div>
                <div class="form-group"><label>Form Teacher</label><select class="form-control" name="teacher_id"><option value="">Not assigned</option><?php foreach ($teachers as $teacher): ?><option value="<?php echo esc_attr($teacher->id); ?>"><?php echo esc_html($teacher->first_name . ' ' . $teacher->last_name); ?></option><?php endforeach; ?></select></div>
            </div>
            <button class="btn btn-primary" type="submit"><i class="fas fa-save"></i> Create Class</button>
        </form>
    </div>
</div>

<div class="card">
    <div class="card-header"><h3>All Classes (<?php echo esc_html(count($classes)); ?>)</h3></div>
    <div class="table-container"><table><thead><tr><th>Name</th><th>Level</th><th>Stream</th><th>Teacher</th><th>Year</th><th>Students / Capacity</th></tr></thead><tbody>
    <?php if ($classes): foreach ($classes as $class): ?>
        <tr><td><strong><?php echo esc_html($class->name); ?></strong></td><td><?php echo esc_html($class->level ?: '-'); ?></td><td><?php echo esc_html($class->stream ?: '-'); ?></td><td><?php echo esc_html($class->teacher_name ?: 'Not assigned'); ?></td><td><?php echo esc_html($class->academic_year ?: '-'); ?></td><td><?php echo esc_html($class->student_count . ' / ' . $class->capacity); ?></td></tr>
    <?php endforeach; else: ?><tr><td colspan="6" class="text-center" style="padding:30px;color:var(--text-light)">No classes have been created.</td></tr><?php endif; ?>
    </tbody></table></div>
</div>
