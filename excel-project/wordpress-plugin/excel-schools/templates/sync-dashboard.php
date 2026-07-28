<?php
/**
 * Sync Center dashboard — vars provided by esm_page_sync_dashboard():
 * $pending, $synced, $failed, $last_sync, $last_status, $flask_endpoint,
 * $sync_enabled, $recent.
 */
if (!defined('ABSPATH')) exit;
?>
<div class="wrap">
    <h1>Excel Schools — Sync Center</h1>
    <p>Bidirectional sync between this WordPress site and the offline Flask app at <code><?php echo esc_html($flask_endpoint ?: 'not configured'); ?></code>.</p>

    <div style="display:flex;gap:16px;margin:20px 0;flex-wrap:wrap;">
        <div class="card" style="padding:16px 24px;background:#fff;border:1px solid #ccd0d4;border-radius:6px;">
            <div style="font-size:24px;font-weight:700;color:#d97706;"><?php echo esc_html($pending); ?></div>
            <div>Pending</div>
        </div>
        <div class="card" style="padding:16px 24px;background:#fff;border:1px solid #ccd0d4;border-radius:6px;">
            <div style="font-size:24px;font-weight:700;color:#059669;"><?php echo esc_html($synced); ?></div>
            <div>Synced</div>
        </div>
        <div class="card" style="padding:16px 24px;background:#fff;border:1px solid #ccd0d4;border-radius:6px;">
            <div style="font-size:24px;font-weight:700;color:#dc2626;"><?php echo esc_html($failed); ?></div>
            <div>Failed</div>
        </div>
    </div>

    <p><strong>Last sync:</strong> <?php echo esc_html($last_sync); ?> — <strong>Status:</strong> <?php echo esc_html($last_status); ?></p>
    <p><strong>Auto-sync:</strong> <?php echo $sync_enabled ? 'Enabled' : 'Disabled'; ?></p>

    <div style="margin:20px 0;">
        <button class="button button-primary" id="esm-push-btn">Push Pending to Flask</button>
        <button class="button" id="esm-pull-btn">Pull from Flask</button>
        <button class="button button-secondary" id="esm-full-sync-btn">Run Full Sync</button>
        <button class="button" id="esm-handshake-btn">Test Handshake</button>
        <button class="button" id="esm-test-btn">Test Connection</button>
    </div>
    <div id="esm-sync-result" style="margin-top:10px;"></div>

    <h2>Recent Sync Log</h2>
    <table class="widefat striped">
        <thead><tr><th>Entity</th><th>Action</th><th>Status</th><th>Created</th></tr></thead>
        <tbody>
            <?php if ($recent): foreach ($recent as $log): ?>
            <tr>
                <td><?php echo esc_html($log->entity_type); ?> #<?php echo esc_html($log->entity_id); ?></td>
                <td><?php echo esc_html($log->action); ?></td>
                <td><?php echo esc_html($log->sync_status); ?></td>
                <td><?php echo esc_html($log->created_at); ?></td>
            </tr>
            <?php endforeach; else: ?>
            <tr><td colspan="4">No sync activity yet.</td></tr>
            <?php endif; ?>
        </tbody>
    </table>
</div>

<script>
(function () {
    var nonce = '<?php echo esc_js(wp_create_nonce('esm_nonce')); ?>';
    var ajaxUrl = '<?php echo esc_url(admin_url('admin-ajax.php')); ?>';
    
    function call(action) {
        document.getElementById('esm-sync-result').textContent = 'Working...';
        var data = new FormData();
        data.append('action', action);
        data.append('nonce', nonce);
        fetch(ajaxUrl, { method: 'POST', body: data, credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (res) {
                document.getElementById('esm-sync-result').innerHTML = '<pre>' + JSON.stringify(res.data || res, null, 2) + '</pre>';
            })
            .catch(function (e) { document.getElementById('esm-sync-result').textContent = 'Error: ' + e; });
    }
    
    document.getElementById('esm-push-btn').onclick = function () { call('esm_push_all'); };
    document.getElementById('esm-pull-btn').onclick = function () { call('esm_pull_all'); };
    document.getElementById('esm-full-sync-btn').onclick = function () { call('esm_full_sync'); };
    document.getElementById('esm-test-btn').onclick = function () { call('esm_test_connection'); };
    
    // NEW: Handshake button
    document.getElementById('esm-handshake-btn').onclick = function () {
        document.getElementById('esm-sync-result').textContent = 'Testing handshake...';
        var data = new FormData();
        data.append('action', 'esm_handshake');
        data.append('nonce', nonce);
        fetch(ajaxUrl, { method: 'POST', body: data, credentials: 'same-origin' })
            .then(r => r.json())
            .then(res => {
                document.getElementById('esm-sync-result').innerHTML = 
                    '<div style="background:#e6ffed;padding:12px;border-radius:6px;">' +
                    '<strong>Handshake Result:</strong><br>' + 
                    JSON.stringify(res.data || res, null, 2) + '</div>';
            })
            .catch(e => document.getElementById('esm-sync-result').textContent = 'Error: ' + e);
    };
})();
</script>
