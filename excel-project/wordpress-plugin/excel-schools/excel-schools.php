<?php
/**
 * Plugin Name: Excel Schools
 * Plugin URI: https://crm.egs.ac.zw
 * Description: Excel Schools management portal for WordPress — a direct mirror of the
 *              offline Flask school-management app, exposed at /sms/ on this site, kept
 *              in sync with the offline app via the bundled sync engine and REST API.
 * Version: 3.1.4
 * Author: Valentine T Mabheka
 * Author URI: https://excelgroup.edu.zw
 * License: GPL v2 or later
 * Text Domain: excel-schools
 * Requires at least: 5.8
 * Requires PHP: 7.4
 */

if (!defined('ABSPATH')) {
    exit;
}

define('ESM_VERSION', '3.1.4');
define('ESM_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('ESM_PLUGIN_URL', plugin_dir_url(__FILE__));
define('ESM_PLUGIN_FILE', __FILE__);
define('ESM_AUTHOR', 'Valentine T Mabheka');

// ─── Roles mirrored 1:1 from the offline app's ROLE_LABELS (app.py) ────
// The offline Flask app recognises exactly these 6 roles. This plugin
// intentionally uses the exact same role keys (prefixed esm_) so that a
// person's role means the same thing, and grants the same access, on
// both systems.
function esm_role_labels() {
    return [
        'esm_super_admin' => 'Super Admin',
        'esm_accountant'  => 'Accountant',
        'esm_bursar'      => 'Bursar',
        'esm_teacher'     => 'Teacher',
        'esm_parent'      => 'Parent',
        'esm_student'     => 'Student',
    ];
}

// ─── Activation / Deactivation ─────────────────────────────────────────

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
    if (!get_option('esm_conflict_strategy')) update_option('esm_conflict_strategy', 'newest_wins');
    if (!get_option('esm_sync_enabled'))    update_option('esm_sync_enabled', true);
    if (!get_option('esm_webhook_enabled')) update_option('esm_webhook_enabled', false);

    set_transient('esm_activated', true, 30);
}

function esm_deactivate() {
    wp_clear_scheduled_hook('esm_scheduled_sync');
    wp_clear_scheduled_hook('esm_health_check');
    flush_rewrite_rules();
}

/**
 * Roles mirror the offline app's role set. Capabilities map 1:1 onto the
 * ROLE_NAV_ITEMS groups in app.py so each role sees the same modules on
 * both systems.
 */
function esm_setup_roles() {
    $all_caps = [
        'esm_manage_settings', 'esm_manage_sync', 'esm_manage_users',
        'esm_manage_students', 'esm_manage_staff', 'esm_manage_fees',
        'esm_manage_exams', 'esm_manage_hostel', 'esm_manage_timetable',
        'esm_manage_communication', 'esm_manage_reports', 'esm_view_dashboard',
    ];

    // Super Admin — full access (mirrors offline 'super_admin')
    add_role('esm_super_admin', 'Excel Schools: Super Admin', ['read' => true]);
    $r = get_role('esm_super_admin');
    foreach ($all_caps as $cap) { $r->add_cap($cap); }

    // Accountant — fees, fee levels, reports, communication (view)
    add_role('esm_accountant', 'Excel Schools: Accountant', ['read' => true]);
    $r = get_role('esm_accountant');
    foreach (['esm_manage_fees', 'esm_manage_reports', 'esm_manage_communication', 'esm_view_dashboard'] as $cap) { $r->add_cap($cap); }

    // Bursar — students, fees, communication, reports
    add_role('esm_bursar', 'Excel Schools: Bursar', ['read' => true]);
    $r = get_role('esm_bursar');
    foreach (['esm_manage_students', 'esm_manage_fees', 'esm_manage_communication', 'esm_manage_reports', 'esm_manage_sync', 'esm_view_dashboard'] as $cap) { $r->add_cap($cap); }

    // Teacher — exams, timetable (view), communication (view), reports
    add_role('esm_teacher', 'Excel Schools: Teacher', ['read' => true]);
    $r = get_role('esm_teacher');
    foreach (['esm_manage_exams', 'esm_manage_communication', 'esm_manage_reports', 'esm_view_dashboard', 'esm_teacher'] as $cap) { $r->add_cap($cap); }

    // Parent — portal only
    add_role('esm_parent', 'Excel Schools: Parent', ['read' => true]);
    $r = get_role('esm_parent');
    $r->add_cap('esm_view_dashboard');

    // Student — portal only
    add_role('esm_student', 'Excel Schools: Student', ['read' => true]);
    $r = get_role('esm_student');
    $r->add_cap('esm_view_dashboard');

    // Grant everything to WP administrators too, so site admins are never locked out.
    $admin = get_role('administrator');
    if ($admin) {
        foreach ($all_caps as $cap) { $admin->add_cap($cap); }
    }
}

/**
 * Reconcile role capabilities after in-place plugin updates. WordPress does
 * not run activation hooks during an update, so existing bursar roles need
 * this one-time migration to receive sync access.
 */
function esm_maybe_upgrade_roles() {
    if (get_option('esm_roles_version') === ESM_VERSION) {
        return;
    }

    esm_setup_roles();
    ESM_Database::seed_defaults();
    global $wpdb;
    $staff_subject_table = $wpdb->prefix . 'esm_staff_subjects';
    $has_sync_id = $wpdb->get_var("SHOW COLUMNS FROM {$staff_subject_table} LIKE 'sync_id'");
    if (!$has_sync_id) {
        $wpdb->query("ALTER TABLE {$staff_subject_table} ADD COLUMN sync_id VARCHAR(36) DEFAULT NULL");
    }
    update_option('esm_roles_version', ESM_VERSION);
}
add_action('init', 'esm_maybe_upgrade_roles', 5);

// ─── Cron scheduling for periodic sync ─────────────────────────────────

function esm_schedule_cron() {
    $interval_map = ['1min' => 60, '5min' => 300, '15min' => 900, '30min' => 1800, 'hourly' => 3600];
    $interval = get_option('esm_sync_interval', '5min');
    $seconds  = $interval_map[$interval] ?? 300;

    add_filter('cron_schedules', function ($schedules) use ($seconds, $interval) {
        if (!isset($schedules[$interval])) {
            $schedules[$interval] = ['interval' => $seconds, 'display' => "Every $interval"];
        }
        return $schedules;
    });

    if (!wp_next_scheduled('esm_scheduled_sync')) {
        wp_schedule_event(time(), $interval, 'esm_scheduled_sync');
    }
    if (!wp_next_scheduled('esm_health_check')) {
        wp_schedule_event(time(), 'hourly', 'esm_health_check');
    }
}

add_action('esm_scheduled_sync', function () {
    if (get_option('esm_sync_enabled', true)) {
        ESM_Sync_Engine::run_sync();
    }
});

add_action('esm_health_check', function () {
    $endpoint = get_option('esm_flask_endpoint', '');
    $api_key  = get_option('esm_sync_api_key', '');
    if (!$endpoint) return;
    $resp = wp_remote_get(rtrim($endpoint, '/') . '/api/stats', [
        'timeout' => 10, 'headers' => ['X-ESM-API-Key' => $api_key],
    ]);
    update_option('esm_flask_reachable', !is_wp_error($resp) && wp_remote_retrieve_response_code($resp) < 400);
});

// ─── Load includes ──────────────────────────────────────────────────────

require_once ESM_PLUGIN_DIR . 'includes/class-database.php';
require_once ESM_PLUGIN_DIR . 'includes/class-helpers.php';
require_once ESM_PLUGIN_DIR . 'includes/class-rest-api.php';
require_once ESM_PLUGIN_DIR . 'includes/class-sync-engine.php';
require_once ESM_PLUGIN_DIR . 'includes/class-webhook-handler.php';
require_once ESM_PLUGIN_DIR . 'includes/class-portal.php';

ESM_Portal::init();
ESM_REST_API::init();
ESM_Webhook_Handler::init();

// Ensure Application Passwords are available even on plain-HTTP dev/staging
// sites. WordPress core disables them unless the site is HTTPS or its
// environment type is 'local' — but the automated bind tool (bind.py)
// needs them to authenticate the offline Flask app without a pre-shared
// secret. This only *allows* the feature; users still opt in per-account
// by creating an Application Password in their WP profile.
add_filter('wp_is_application_passwords_available', '__return_true');

// ─── wp-admin: Settings & Sync Center menu (data entry stays on the
//     frontend /sms/ portal — wp-admin only hosts configuration) ───────

add_action('admin_menu', 'esm_admin_menu');
function esm_admin_menu() {
    // The parent menu must be visible to every Excel Schools user. Each
    // submenu retains its own capability check, so bursars can reach Sync
    // Center without gaining access to system settings.
    add_menu_page(
        'Excel Schools',
        'Excel Schools',
        'esm_view_dashboard',
        'excel-schools',
        'esm_page_admin_landing',
        'dashicons-welcome-learn-more',
        30
    );
    add_submenu_page('excel-schools', 'Excel Schools', 'Overview', 'esm_view_dashboard', 'excel-schools', 'esm_page_admin_landing');
    add_submenu_page('excel-schools', 'Settings', 'Settings', 'esm_manage_settings', 'excel-schools-settings', 'esm_page_settings');
    add_submenu_page('excel-schools', 'Sync Center', 'Sync Center & JSON Import', 'esm_manage_sync', 'excel-schools-sync', 'esm_page_sync_dashboard');
    add_submenu_page('excel-schools', 'Sync Settings', 'Sync Settings', 'esm_manage_sync', 'excel-schools-sync-settings', 'esm_page_sync_settings');
    add_submenu_page('excel-schools', 'Sync Logs', 'Sync Logs', 'esm_manage_sync', 'excel-schools-sync-logs', 'esm_page_sync_logs');
    add_submenu_page('excel-schools', 'Open Portal', '⇱ Open Portal (/sms/)', 'esm_view_dashboard', 'excel-schools-portal-link', 'esm_portal_link_page');
}

function esm_page_admin_landing() {
    $portal_url = esc_url(home_url('/sms/'));
    echo '<div class="wrap"><h1>Excel Schools</h1><p>Open your role dashboard or manage synchronization.</p>';
    echo '<p><a href="' . $portal_url . '" class="button button-primary">Open Online Portal</a> ';
    if (current_user_can('esm_manage_sync')) {
        echo '<a href="' . esc_url(admin_url('admin.php?page=excel-schools-sync')) . '" class="button">Sync Center &amp; JSON Import</a> ';
    }
    if (current_user_can('esm_manage_settings')) {
        echo '<a href="' . esc_url(admin_url('admin.php?page=excel-schools-settings')) . '" class="button">Settings</a>';
    }
    echo '</p></div>';
}

function esm_portal_link_page() {
    $url = esc_url(home_url('/sms/'));
    echo '<script>window.open("' . $url . '", "_blank");</script>';
    echo '<div class="wrap"><h2>Portal Opening...</h2><p>The Excel Schools portal has been opened in a new tab.</p><p><a href="' . $url . '" target="_blank" class="button button-primary">Open Portal Again</a></p></div>';
}

function esm_page_settings() {
    include ESM_PLUGIN_DIR . 'templates/settings.php';
}

function esm_process_manual_json_upload($field_name = 'json_file') {
    if (!current_user_can('esm_manage_sync')) {
        return ['error' => 'You do not have permission to import synchronization data.'];
    }
    if (empty($_FILES[$field_name]) || empty($_FILES[$field_name]['tmp_name'])) {
        return ['error' => 'Select a JSON export file to import.'];
    }
    if ((int) ($_FILES[$field_name]['error'] ?? UPLOAD_ERR_OK) !== UPLOAD_ERR_OK) {
        return ['error' => 'The JSON file upload failed. Please try again.'];
    }
    if ((int) ($_FILES[$field_name]['size'] ?? 0) > 16 * 1024 * 1024) {
        return ['error' => 'The JSON export exceeds the 16 MB upload limit.'];
    }

    $filename = sanitize_file_name($_FILES[$field_name]['name'] ?? '');
    if (strtolower(pathinfo($filename, PATHINFO_EXTENSION)) !== 'json') {
        return ['error' => 'Only .json sync export files are accepted.'];
    }
    $content = file_get_contents($_FILES[$field_name]['tmp_name']);
    $payload = json_decode($content, true);
    if (json_last_error() !== JSON_ERROR_NONE || !is_array($payload)) {
        return ['error' => 'The uploaded file does not contain valid JSON.'];
    }
    return ESM_Sync_Engine::import_json_payload($payload);
}

function esm_page_sync_dashboard() {
    global $wpdb;
    $pfx = $wpdb->prefix;
    $import_result = null;
    if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['esm_sync_json_import'])) {
        check_admin_referer('esm_sync_json_import', 'esm_sync_import_nonce');
        $import_result = esm_process_manual_json_upload('sync_json_file');
    }
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
        update_option('esm_conflict_strategy', sanitize_text_field($_POST['conflict_strategy']));
        update_option('esm_sync_enabled', isset($_POST['sync_enabled']));
        update_option('esm_webhook_enabled', isset($_POST['webhook_enabled']));
        wp_clear_scheduled_hook('esm_scheduled_sync');
        esm_schedule_cron();
        echo '<div class="notice notice-success"><p>Sync settings saved.</p></div>';
    }
    $flask_endpoint    = get_option('esm_flask_endpoint', 'http://localhost:5000');
    $sync_api_key      = get_option('esm_sync_api_key', '');
    $sync_interval     = get_option('esm_sync_interval', '5min');
    $conflict_strategy = get_option('esm_conflict_strategy', 'newest_wins');
    $sync_enabled      = get_option('esm_sync_enabled', true);
    $webhook_enabled   = get_option('esm_webhook_enabled', false);
    include ESM_PLUGIN_DIR . 'templates/sync-settings.php';
}

function esm_page_sync_logs() {
    global $wpdb;
    $pfx = $wpdb->prefix;
    if (isset($_POST['esm_clear_logs'])) {
        check_admin_referer('esm_clear_logs', 'esm_logs_nonce');
        $wpdb->query("TRUNCATE TABLE {$pfx}esm_sync_log");
        echo '<div class="notice notice-success"><p>Sync log cleared.</p></div>';
    }
    $logs = $wpdb->get_results("SELECT * FROM {$pfx}esm_sync_log ORDER BY created_at DESC LIMIT 200");
    include ESM_PLUGIN_DIR . 'templates/sync-logs.php';
}

// ─── AJAX: manual sync triggers from wp-admin ─────────────────────────

add_action('wp_ajax_esm_handshake', function () {
    check_ajax_referer('esm_nonce', 'nonce');
    if (!current_user_can('esm_manage_sync')) wp_send_json_error('Forbidden');
    $endpoint = sanitize_text_field($_POST['endpoint'] ?? get_option('esm_flask_endpoint', ''));
    $api_key  = sanitize_text_field($_POST['api_key'] ?? get_option('esm_sync_api_key', ''));
    wp_send_json_success(ESM_Sync_Engine::handshake($endpoint, $api_key));
});

add_action('wp_ajax_esm_push_all', function () {
    check_ajax_referer('esm_nonce', 'nonce');
    if (!current_user_can('esm_manage_sync')) wp_send_json_error('Forbidden');
    wp_send_json_success(ESM_Sync_Engine::push_all_pending());
});

add_action('wp_ajax_esm_pull_all', function () {
    check_ajax_referer('esm_nonce', 'nonce');
    if (!current_user_can('esm_manage_sync')) wp_send_json_error('Forbidden');
    wp_send_json_success(ESM_Sync_Engine::pull_from_flask());
});

add_action('wp_ajax_esm_full_sync', function () {
    check_ajax_referer('esm_nonce', 'nonce');
    if (!current_user_can('esm_manage_sync')) wp_send_json_error('Forbidden');
    wp_send_json_success(ESM_Sync_Engine::run_sync());
});

add_action('wp_ajax_esm_test_connection', function () {
    check_ajax_referer('esm_nonce', 'nonce');
    if (!current_user_can('esm_manage_sync')) wp_send_json_error('Forbidden');
    $endpoint = sanitize_text_field($_POST['endpoint'] ?? get_option('esm_flask_endpoint', ''));
    $api_key  = sanitize_text_field($_POST['api_key'] ?? get_option('esm_sync_api_key', ''));
    wp_send_json_success(ESM_Sync_Engine::test_connection($endpoint, $api_key));
});
