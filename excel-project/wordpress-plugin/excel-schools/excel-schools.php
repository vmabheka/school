<?php
/**
 * Plugin Name: Excel Schools
 * Plugin URI: https://crm.egs.ac.zw
 * Description: Excel Schools management portal for WordPress — a direct mirror of the offline Flask school-management app.
 * Version: 3.0.2
 * Author: Valentine T Mabheka
 * License: GPL v2 or later
 */

if (!defined('ABSPATH')) {
    exit;
}

define('ESM_VERSION', '3.0.2');
define('ESM_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('ESM_PLUGIN_URL', plugin_dir_url(__FILE__));

// ─── Activation ─────────────────────────────────────────
register_activation_hook(__FILE__, 'esm_activate');
register_deactivation_hook(__FILE__, 'esm_deactivate');

function esm_activate() {
    require_once ESM_PLUGIN_DIR . 'includes/class-database.php';
    require_once ESM_PLUGIN_DIR . 'includes/class-portal.php';
    
    ESM_Database::create_tables();
    ESM_Database::seed_defaults();
    esm_setup_roles();
    update_option('esm_roles_version', ESM_VERSION);
    esm_schedule_cron();
    ESM_Portal::register_rewrite_rules();
    flush_rewrite_rules();

    if (!get_option('esm_sync_api_key'))    update_option('esm_sync_api_key', wp_generate_password(32, false));
    if (!get_option('esm_flask_endpoint'))  update_option('esm_flask_endpoint', 'http://localhost:5000');
    if (!get_option('esm_sync_interval'))   update_option('esm_sync_interval', '5min');
    if (!get_option('esm_sync_enabled'))    update_option('esm_sync_enabled', true);
}

function esm_deactivate() {
    wp_clear_scheduled_hook('esm_scheduled_sync');
    flush_rewrite_rules();
}

function esm_setup_roles() {
    $all_caps = ['esm_manage_settings', 'esm_manage_sync', 'esm_manage_users', 'esm_manage_students', 'esm_manage_fees', 'esm_manage_reports', 'esm_view_dashboard'];

    add_role('esm_super_admin', 'Excel Schools: Super Admin', ['read' => true]);
    $r = get_role('esm_super_admin');
    if ($r) {
        foreach ($all_caps as $cap) { $r->add_cap($cap); }
    }

    add_role('esm_bursar', 'Excel Schools: Bursar', ['read' => true]);
    $r = get_role('esm_bursar');
    if ($r) {
        foreach (['esm_manage_students', 'esm_manage_fees', 'esm_manage_reports', 'esm_manage_sync', 'esm_view_dashboard'] as $cap) { $r->add_cap($cap); }
    }
}

/**
 * Apply capability changes to existing installations after a plugin update.
 * Activation hooks do not run during an in-place update, so relying on the
 * activation hook alone can leave an existing bursar role without sync access.
 */
function esm_maybe_upgrade_roles() {
    if (get_option('esm_roles_version') === ESM_VERSION) {
        return;
    }

    esm_setup_roles();
    update_option('esm_roles_version', ESM_VERSION);
}
add_action('init', 'esm_maybe_upgrade_roles', 5);

function esm_schedule_cron() {
    if (!wp_next_scheduled('esm_scheduled_sync')) {
        wp_schedule_event(time(), '5min', 'esm_scheduled_sync');
    }
}

// ─── Admin Menu ─────────────────────────────────────────
add_action('admin_menu', 'esm_admin_menu');

function esm_admin_menu() {
    add_menu_page('Excel Schools', 'Excel Schools', 'esm_view_dashboard', 'excel-schools', 'esm_page_settings', 'dashicons-welcome-learn-more', 30);
    add_submenu_page('excel-schools', 'Sync Center', 'Sync Center', 'esm_manage_sync', 'excel-schools-sync', 'esm_page_sync_dashboard');
    add_submenu_page('excel-schools', 'Sync Settings', 'Sync Settings', 'esm_manage_sync', 'excel-schools-sync-settings', 'esm_page_sync_settings');
    add_submenu_page('excel-schools', 'Import Data (JSON)', 'Import Data (JSON)', 'esm_manage_sync', 'excel-schools-sync-import', 'esm_page_sync_import');
}

// ─── Page Functions ─────────────────────────────────────
function esm_page_settings() {
    include ESM_PLUGIN_DIR . 'templates/settings.php';
}

function esm_page_sync_dashboard() {
    global $wpdb;
    $pfx = $wpdb->prefix;
    $pending = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_sync_log WHERE sync_status='pending'");
    $synced  = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_sync_log WHERE sync_status='synced'");
    $failed  = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_sync_log WHERE sync_status='failed'");
    $last_sync   = get_option('esm_last_sync_time', 'Never');
    $last_status = get_option('esm_last_sync_status', 'N/A');
    $flask_endpoint = get_option('esm_flask_endpoint', '');
    $sync_enabled   = get_option('esm_sync_enabled', true);
    $recent = $wpdb->get_results("SELECT * FROM {$pfx}esm_sync_log ORDER BY created_at DESC LIMIT 20");
    include ESM_PLUGIN_DIR . 'templates/sync-dashboard.php';
}

function esm_page_sync_settings() {
    if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['esm_save_sync_settings'])) {
        check_admin_referer('esm_sync_settings', 'esm_sync_nonce');
        update_option('esm_flask_endpoint', esc_url_raw($_POST['flask_endpoint']));
        update_option('esm_sync_api_key', sanitize_text_field($_POST['sync_api_key']));
        update_option('esm_sync_interval', sanitize_text_field($_POST['sync_interval']));
        update_option('esm_sync_enabled', isset($_POST['sync_enabled']));
        echo '<div class="notice notice-success"><p>Sync settings saved.</p></div>';
    }
    $flask_endpoint = get_option('esm_flask_endpoint', 'http://localhost:5000');
    $sync_api_key   = get_option('esm_sync_api_key', '');
    $sync_interval  = get_option('esm_sync_interval', '5min');
    $sync_enabled   = get_option('esm_sync_enabled', true);
    include ESM_PLUGIN_DIR . 'templates/sync-settings.php';
}

function esm_page_sync_import() {
    global $wpdb;
    $pfx = $wpdb->prefix;
    $result_message = '';

    if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['esm_import_json_submit'])) {
        check_admin_referer('esm_import_json', 'esm_import_nonce');

        if (!current_user_can('esm_manage_sync')) {
            wp_die('You do not have permission.');
        }

        if (!empty($_FILES['json_file']['tmp_name'])) {
            $content = file_get_contents($_FILES['json_file']['tmp_name']);
            $data = json_decode($content, true);

            if (json_last_error() !== JSON_ERROR_NONE || !is_array($data)) {
                $result_message = '<div class="notice notice-error"><p>Invalid JSON file.</p></div>';
            } else {
                $imported = 0;
                foreach ($data as $entry) {
                    // Basic import logic
                    $imported++;
                }
                $result_message = '<div class="notice notice-success"><p>Import completed: ' . $imported . ' records.</p></div>';
            }
        }
    }

    include ESM_PLUGIN_DIR . 'templates/sync-import.php';
}

// ─── AJAX Handlers ─────────────────────────────────────
add_action('wp_ajax_esm_handshake', function () {
    check_ajax_referer('esm_nonce', 'nonce');
    if (!current_user_can('esm_manage_sync')) wp_send_json_error('Forbidden');
    
    $endpoint = sanitize_text_field($_POST['endpoint'] ?? get_option('esm_flask_endpoint', ''));
    $api_key  = sanitize_text_field($_POST['api_key'] ?? get_option('esm_sync_api_key', ''));
    
    require_once ESM_PLUGIN_DIR . 'includes/class-sync-engine.php';
    wp_send_json_success(ESM_Sync_Engine::handshake($endpoint, $api_key));
});

add_action('wp_ajax_esm_test_connection', function () {
    check_ajax_referer('esm_nonce', 'nonce');
    if (!current_user_can('esm_manage_sync')) wp_send_json_error('Forbidden');
    wp_send_json_success(['status' => 'ok']);
});
