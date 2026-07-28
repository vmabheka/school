<?php
/**
 * Sync Settings — vars from esm_page_sync_settings(): $flask_endpoint,
 * $sync_api_key, $sync_interval, $conflict_strategy, $sync_enabled,
 * $webhook_enabled.
 */
if (!defined('ABSPATH')) exit;
?>
<div class="wrap">
    <h1>Excel Schools — Sync Settings</h1>
    <form method="POST">
        <?php wp_nonce_field('esm_sync_settings', 'esm_sync_nonce'); ?>
        <table class="form-table">
            <tr><th>Flask Server Endpoint</th><td><input type="url" name="flask_endpoint" class="regular-text" value="<?php echo esc_attr($flask_endpoint); ?>" placeholder="http://localhost:5000"></td></tr>
            <tr><th>Sync API Key</th><td><input type="text" name="sync_api_key" class="regular-text" value="<?php echo esc_attr($sync_api_key); ?>"><p class="description">Must match the API key configured on the Flask side (SYNC_API_KEY env var / Sync settings page).</p></td></tr>
            <tr><th>Sync Interval</th><td>
                <select name="sync_interval">
                    <?php foreach (['1min' => 'Every 1 minute', '5min' => 'Every 5 minutes', '15min' => 'Every 15 minutes', '30min' => 'Every 30 minutes', 'hourly' => 'Hourly'] as $val => $label): ?>
                    <option value="<?php echo esc_attr($val); ?>" <?php selected($sync_interval, $val); ?>><?php echo esc_html($label); ?></option>
                    <?php endforeach; ?>
                </select>
            </td></tr>
            <tr><th>Conflict Resolution</th><td>
                <select name="conflict_strategy">
                    <option value="newest_wins" <?php selected($conflict_strategy, 'newest_wins'); ?>>Newest modification wins (recommended)</option>
                    <option value="wp_wins" <?php selected($conflict_strategy, 'wp_wins'); ?>>WordPress always wins</option>
                    <option value="flask_wins" <?php selected($conflict_strategy, 'flask_wins'); ?>>Flask (offline) always wins</option>
                </select>
            </td></tr>
            <tr><th>Auto Sync</th><td><label><input type="checkbox" name="sync_enabled" <?php checked($sync_enabled); ?>> Enable scheduled sync</label></td></tr>
            <tr><th>Webhooks</th><td><label><input type="checkbox" name="webhook_enabled" <?php checked($webhook_enabled); ?>> Push real-time webhooks on data change</label></td></tr>
        </table>
        <?php submit_button('Save Sync Settings', 'primary', 'esm_save_sync_settings'); ?>
    </form>
</div>
