<?php
/** Sync Logs — vars from esm_page_sync_logs(): $logs */
if (!defined('ABSPATH')) exit;
?>
<div class="wrap">
    <h1>Excel Schools — Sync Logs</h1>
    <form method="POST" style="margin-bottom:16px;">
        <?php wp_nonce_field('esm_clear_logs', 'esm_logs_nonce'); ?>
        <button type="submit" name="esm_clear_logs" class="button button-secondary" onclick="return confirm('Clear all sync logs?');">Clear Logs</button>
    </form>
    <table class="widefat striped">
        <thead><tr><th>ID</th><th>Entity</th><th>Action</th><th>Status</th><th>Created</th><th>Synced At</th></tr></thead>
        <tbody>
            <?php if ($logs): foreach ($logs as $log): ?>
            <tr>
                <td><?php echo esc_html($log->id); ?></td>
                <td><?php echo esc_html($log->entity_type); ?> #<?php echo esc_html($log->entity_id); ?></td>
                <td><?php echo esc_html($log->action); ?></td>
                <td><?php echo esc_html($log->sync_status); ?></td>
                <td><?php echo esc_html($log->created_at); ?></td>
                <td><?php echo esc_html($log->sync_timestamp); ?></td>
            </tr>
            <?php endforeach; else: ?>
            <tr><td colspan="6">No sync logs.</td></tr>
            <?php endif; ?>
        </tbody>
    </table>
</div>
