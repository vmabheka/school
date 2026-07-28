<?php
/** Timetable — port of the offline app's timetable_view() route/template. */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;
$classes = $wpdb->get_results("SELECT id, name FROM {$pfx}esm_classes ORDER BY name");
$class_id = intval($_GET['class_id'] ?? 0);
$slots = $class_id ? $wpdb->get_results($wpdb->prepare(
    "SELECT t.*, sub.name AS subject_name FROM {$pfx}esm_timetable_slots t LEFT JOIN {$pfx}esm_subjects sub ON sub.id = t.subject_id WHERE t.class_id=%d ORDER BY FIELD(t.day_of_week,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'), t.period", $class_id)) : [];
?>
<div class="page-header"><div><h1>Timetable</h1><p>View class timetables</p></div></div>

<div class="filter-bar" style="margin-bottom:16px;">
    <form method="GET" style="display:flex;gap:8px;align-items:center;">
        <select name="class_id" class="form-control" onchange="this.form.submit()">
            <option value="">Select a class...</option>
            <?php foreach ($classes as $c): ?>
            <option value="<?php echo esc_attr($c->id); ?>" <?php selected($class_id, $c->id); ?>><?php echo esc_html($c->name); ?></option>
            <?php endforeach; ?>
        </select>
    </form>
</div>

<div class="card">
    <div class="table-container">
        <table>
            <thead><tr><th>Day</th><th>Period</th><th>Time</th><th>Subject</th><th>Room</th></tr></thead>
            <tbody>
                <?php if ($slots): foreach ($slots as $s): ?>
                <tr>
                    <td><?php echo esc_html($s->day_of_week); ?></td>
                    <td><?php echo esc_html($s->period); ?></td>
                    <td><?php echo esc_html(substr($s->start_time, 0, 5) . ' - ' . substr($s->end_time, 0, 5)); ?></td>
                    <td><?php echo esc_html($s->subject_name ?: '-'); ?></td>
                    <td><?php echo esc_html($s->room ?: '-'); ?></td>
                </tr>
                <?php endforeach; else: ?>
                <tr><td colspan="5" class="text-center" style="padding:30px;color:var(--text-light);"><?php echo $class_id ? 'No timetable slots for this class' : 'Select a class to view its timetable'; ?></td></tr>
                <?php endif; ?>
            </tbody>
        </table>
    </div>
</div>
