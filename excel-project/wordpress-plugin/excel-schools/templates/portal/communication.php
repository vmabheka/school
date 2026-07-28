<?php
/** Communication — port of the offline app's templates/communication/dashboard.html. */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;
$notices = $wpdb->get_results("SELECT * FROM {$pfx}esm_notices WHERE is_active=1 ORDER BY date_posted DESC LIMIT 20");
$messages = $wpdb->get_results($wpdb->prepare(
    "SELECT m.*, u.user_login AS sender_login FROM {$pfx}esm_messages m
     LEFT JOIN {$wpdb->users} u ON u.ID = m.sender_id
     WHERE m.recipient_id = %d OR m.sender_id = %d ORDER BY m.date_sent DESC LIMIT 20",
    $user->ID, $user->ID
));
$category_badge = ['General' => 'badge-info', 'Urgent' => 'badge-warning', 'Academic' => 'badge-primary'];
?>
<div class="page-header">
    <div><h1>Communication</h1><p>Notices, messages, and announcements</p></div>
    <div class="actions">
        <?php if ($role === 'esm_super_admin'): ?>
        <a href="<?php echo esc_url(home_url('/sms/communication/?action=notice')); ?>" class="btn btn-primary"><i class="fas fa-bullhorn"></i> Post Notice</a>
        <?php endif; ?>
    </div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
    <div class="card">
        <div class="card-header"><h3><i class="fas fa-bullhorn" style="color:var(--accent);margin-right:8px;"></i>Notices</h3></div>
        <div class="card-body">
            <?php if ($notices): foreach ($notices as $n): ?>
            <div style="padding:12px 0;border-bottom:1px solid var(--border);">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <strong><?php echo esc_html($n->title); ?></strong>
                    <span class="badge <?php echo esc_attr($category_badge[$n->category] ?? 'badge-secondary'); ?>"><?php echo esc_html($n->category); ?></span>
                </div>
                <p style="font-size:12px;color:var(--text-light);margin-top:4px;"><?php echo esc_html(mb_strimwidth(wp_strip_all_tags($n->content), 0, 150, '...')); ?></p>
                <p style="font-size:11px;color:var(--text-light);margin-top:4px;">Posted: <?php echo esc_html(mysql2date('M j, Y', $n->date_posted)); ?> &bull; For: <?php echo esc_html($n->target_audience); ?></p>
            </div>
            <?php endforeach; else: ?>
            <p style="color:var(--text-light);text-align:center;padding:20px;">No notices</p>
            <?php endif; ?>
        </div>
    </div>

    <div class="card">
        <div class="card-header"><h3><i class="fas fa-envelope" style="color:var(--primary);margin-right:8px;"></i>Messages</h3></div>
        <div class="card-body">
            <?php if ($messages): foreach ($messages as $m): ?>
            <div style="padding:12px 0;border-bottom:1px solid var(--border);<?php echo !$m->is_read ? 'background:#f0f7ff;' : ''; ?>">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <strong style="font-size:13px;"><?php echo esc_html($m->subject ?: 'No Subject'); ?></strong>
                    <?php if (!$m->is_read): ?><span class="badge badge-info">New</span><?php endif; ?>
                </div>
                <p style="font-size:12px;color:var(--text-light);margin-top:4px;"><?php echo esc_html(mb_strimwidth((string) $m->body, 0, 100, '...')); ?></p>
                <p style="font-size:11px;color:var(--text-light);margin-top:4px;">From: <?php echo esc_html($m->sender_login ?: 'Unknown'); ?> &bull; <?php echo esc_html(mysql2date('M j, H:i', $m->date_sent)); ?></p>
            </div>
            <?php endforeach; else: ?>
            <p style="color:var(--text-light);text-align:center;padding:20px;">No messages</p>
            <?php endif; ?>
        </div>
    </div>
</div>
