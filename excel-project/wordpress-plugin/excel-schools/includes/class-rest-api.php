<?php
/**
 * ESM REST API — exposes WordPress-side data for sync with the offline
 * Flask app, under the namespace excel-schools/v2 (matches the Flask
 * app's own /api/... route shapes so the two speak the same protocol).
 *
 * Every request is authenticated against the single 'esm_sync_api_key'
 * option — the same option the Sync Engine reads/writes — so there is
 * no key-name mismatch between authentication and configuration.
 *
 * Author: Valentine T Mabheka | Version: 3.0.0
 */
if (!defined('ABSPATH')) exit;

class ESM_REST_API {

    public static function init() {
        add_action('rest_api_init', [__CLASS__, 'register_routes']);
    }

    public static function register_routes() {
        $ns = 'excel-schools/v2';

        register_rest_route($ns, '/sync', [
            'methods' => 'POST', 'callback' => [__CLASS__, 'receive_sync'],
            'permission_callback' => [__CLASS__, 'verify_api_key'],
        ]);
        register_rest_route($ns, '/sync/pending', [
            'methods' => 'GET', 'callback' => [__CLASS__, 'get_pending'],
            'permission_callback' => [__CLASS__, 'verify_api_key'],
        ]);
        register_rest_route($ns, '/sync/mark-synced', [
            'methods' => 'POST', 'callback' => [__CLASS__, 'mark_synced'],
            'permission_callback' => [__CLASS__, 'verify_api_key'],
        ]);
        register_rest_route($ns, '/export/(?P<entity>[a-z_]+)', [
            'methods' => 'GET', 'callback' => [__CLASS__, 'export_entity'],
            'permission_callback' => [__CLASS__, 'verify_api_key'],
        ]);
        register_rest_route($ns, '/import/(?P<entity>[a-z_]+)', [
            'methods' => 'POST', 'callback' => [__CLASS__, 'import_entity'],
            'permission_callback' => [__CLASS__, 'verify_api_key'],
        ]);
        register_rest_route($ns, '/stats', [
            'methods' => 'GET', 'callback' => [__CLASS__, 'get_stats'],
            'permission_callback' => [__CLASS__, 'verify_api_key'],
        ]);
        register_rest_route($ns, '/fee-balance/(?P<student_id>\d+)', [
            'methods' => 'GET', 'callback' => [__CLASS__, 'fee_balance'],
            'permission_callback' => [__CLASS__, 'verify_api_key'],
        ]);
        register_rest_route($ns, '/class-level-info/(?P<class_id>\d+)', [
            'methods' => 'GET', 'callback' => [__CLASS__, 'class_level_info'],
            'permission_callback' => [__CLASS__, 'verify_api_key'],
        ]);
        register_rest_route($ns, '/theme/export', [
            'methods' => 'GET', 'callback' => [__CLASS__, 'theme_export'],
            'permission_callback' => [__CLASS__, 'verify_api_key'],
        ]);
        register_rest_route($ns, '/theme/import', [
            'methods' => 'POST', 'callback' => [__CLASS__, 'theme_import'],
            'permission_callback' => [__CLASS__, 'verify_api_key'],
        ]);

        // One-shot binding endpoint — lets the offline Flask app fetch
        // (or set) the shared sync API key by authenticating as a real
        // WordPress user (via Application Password) instead of already
        // knowing the sync key. This is what makes automated /
        // one-command binding possible: the Flask side only needs a WP
        // username + application password, not a pre-shared secret.
        register_rest_route($ns, '/bind', [
            'methods' => 'POST',
            'callback' => [__CLASS__, 'bind'],
            'permission_callback' => function () {
                return current_user_can('esm_manage_sync') || current_user_can('manage_options');
            },
        ]);
    }

    /**
     * Handle a bind request from the offline Flask app. Requires a real
     * WordPress login (Application Password over Basic Auth) — see
     * permission_callback above. Returns the current sync API key and
     * this site's REST base, and optionally rotates the key first.
     */
    public static function bind($request) {
        $params = $request->get_json_params() ?: [];
        if (!empty($params['rotate_key'])) {
            update_option('esm_sync_api_key', wp_generate_password(32, false));
        }
        $api_key = get_option('esm_sync_api_key', '');
        if (empty($api_key)) {
            $api_key = wp_generate_password(32, false);
            update_option('esm_sync_api_key', $api_key);
        }
        if (!empty($params['flask_endpoint'])) {
            update_option('esm_flask_endpoint', esc_url_raw($params['flask_endpoint']));
        }
        return rest_ensure_response([
            'success' => true,
            'site_name' => get_bloginfo('name'),
            'rest_base' => rest_url('excel-schools/v2'),
            'sms_url' => home_url('/sms/'),
            'sync_api_key' => $api_key,
            'version' => ESM_VERSION,
        ]);
    }

    public static function verify_api_key($request) {
        $api_key = $request->get_header('X-ESM-API-Key');
        if (!$api_key) {
            $params = $request->get_json_params();
            $api_key = $params['api_key'] ?? $request->get_param('api_key');
        }
        $stored_key = get_option('esm_sync_api_key', '');
        return !empty($stored_key) && $api_key === $stored_key;
    }

    // ─── Entity <-> table map, mirrors app.py's own export/import maps ──
    private static function table_map() {
        return [
            'students'       => 'esm_students',
            'staff'          => 'esm_staff',
            'fee_payments'   => 'esm_fee_payments',
            'fee_levels'     => 'esm_fee_levels',
            'fee_structures' => 'esm_fee_structures',
            'classes'        => 'esm_classes',
            'subjects'       => 'esm_subjects',
            'academic_years' => 'esm_academic_years',
            'terms'          => 'esm_terms',
            'exam_results'   => 'esm_exam_results',
            'notices'        => 'esm_notices',
            'invoices'       => 'esm_invoices',
            'invoice_items'  => 'esm_invoice_items',
        ];
    }

    private static function entity_type_table_map() {
        return [
            'Student' => 'esm_students', 'Staff' => 'esm_staff',
            'FeePayment' => 'esm_fee_payments', 'ExamResult' => 'esm_exam_results',
            'Notice' => 'esm_notices', 'FeeStructure' => 'esm_fee_structures',
            'FeeLevel' => 'esm_fee_levels', 'Class' => 'esm_classes',
            'Subject' => 'esm_subjects', 'AcademicYear' => 'esm_academic_years',
            'Term' => 'esm_terms', 'Invoice' => 'esm_invoices',
        ];
    }

    public static function theme_export($request) {
        return new WP_REST_Response([
            'success' => true, 'theme' => ESM_Helpers::get_theme(),
            'updated_at' => current_time('mysql'), 'version' => ESM_VERSION,
        ], 200);
    }

    public static function theme_import($request) {
        $params = $request->get_json_params();
        $theme = $params['theme'] ?? [];
        if (!is_array($theme) || empty($theme)) {
            return new WP_Error('no_theme', 'theme payload missing', ['status' => 400]);
        }
        global $wpdb;
        $pfx = $wpdb->prefix;
        $allowed = array_keys(ESM_Helpers::default_theme());
        $applied = []; $skipped = [];
        foreach ($theme as $key => $value) {
            if (!in_array($key, $allowed, true)) { $skipped[] = $key; continue; }
            $value = sanitize_text_field($value);
            $exists = $wpdb->get_var($wpdb->prepare("SELECT id FROM {$pfx}esm_appearance_settings WHERE setting_key=%s", $key));
            if ($exists) {
                $wpdb->update("{$pfx}esm_appearance_settings", ['setting_value' => $value], ['setting_key' => $key]);
            } else {
                $wpdb->insert("{$pfx}esm_appearance_settings", ['setting_key' => $key, 'setting_value' => $value]);
            }
            $applied[] = $key;
        }
        return new WP_REST_Response(['success' => true, 'applied_keys' => $applied, 'skipped_keys' => $skipped], 200);
    }

    /**
     * Receive a single sync event from Flask — mirrors the shape/behavior
     * of the offline app's own /api/sync endpoint (upsert-by-sync_id with
     * newest_wins / wp_wins / flask_wins conflict resolution).
     */
    public static function receive_sync($request) {
        global $wpdb;
        $params = is_array($request) ? $request : $request->get_json_params();
        $entity_type = sanitize_text_field($params['entity_type'] ?? '');
        $action      = sanitize_text_field($params['action'] ?? '');
        $data        = $params['data'] ?? [];
        $sync_id     = sanitize_text_field($params['sync_id'] ?? ($data['sync_id'] ?? ''));
        $incoming_timestamp = $params['timestamp'] ?? '';
        $conflict_strategy  = sanitize_text_field($params['conflict_strategy'] ?? get_option('esm_conflict_strategy', 'newest_wins'));

        if (!$entity_type || !$action) {
            return new WP_Error('missing_params', 'entity_type and action are required', ['status' => 400]);
        }

        $map = self::entity_type_table_map();
        $table_suffix = $map[$entity_type] ?? null;
        if (!$table_suffix) {
            return new WP_Error('unknown_entity', "Unknown entity type: $entity_type", ['status' => 400]);
        }
        $table = $wpdb->prefix . $table_suffix;
        $result = ['status' => 'ok', 'sync_id' => $sync_id];

        if ($action === 'CREATE' || $action === 'UPDATE') {
            $existing = $sync_id ? $wpdb->get_row($wpdb->prepare("SELECT id, updated_at FROM $table WHERE sync_id=%s", $sync_id)) : null;
            $sanitized = [];
            foreach ($data as $k => $v) {
                $sanitized[sanitize_key($k)] = is_string($v) ? sanitize_text_field($v) : $v;
            }
            unset($sanitized['id']);

            if ($existing) {
                $should_update = true;
                if ($conflict_strategy === 'newest_wins' && $incoming_timestamp && !empty($existing->updated_at)) {
                    $should_update = strtotime($incoming_timestamp) > strtotime($existing->updated_at);
                } elseif ($conflict_strategy === 'wp_wins') {
                    $should_update = false;
                }
                if ($should_update) {
                    if (self::has_column($table, 'updated_at')) $sanitized['updated_at'] = current_time('mysql');
                    $wpdb->update($table, $sanitized, ['id' => $existing->id]);
                    $result['action_taken'] = 'UPDATE';
                } else {
                    $result['action_taken'] = 'SKIPPED';
                }
                $result['entity_id'] = $existing->id;
            } else {
                if (self::has_column($table, 'created_at')) $sanitized['created_at'] = current_time('mysql');
                $wpdb->insert($table, $sanitized);
                $result['entity_id'] = $wpdb->insert_id;
                $result['action_taken'] = 'CREATE';
            }
        } elseif ($action === 'DELETE') {
            $entity_id = intval($params['entity_id'] ?? 0);
            if ($entity_id) {
                if (in_array($entity_type, ['Student', 'Staff'], true)) {
                    $wpdb->update($table, ['status' => 'Inactive'], ['id' => $entity_id]);
                } else {
                    $wpdb->delete($table, ['id' => $entity_id]);
                }
                $result['action_taken'] = 'DELETE';
            }
        }

        return rest_ensure_response($result);
    }

    public static function get_pending($request) {
        global $wpdb;
        $logs = $wpdb->get_results("SELECT * FROM {$wpdb->prefix}esm_sync_log WHERE sync_status='pending' ORDER BY created_at ASC LIMIT 500");
        $items = [];
        foreach ($logs as $log) {
            $items[] = [
                'id' => $log->id, 'entity_type' => $log->entity_type, 'entity_id' => $log->entity_id,
                'action' => $log->action, 'data' => json_decode($log->data_snapshot, true),
                'created_at' => $log->created_at,
            ];
        }
        return rest_ensure_response(['pending' => $items, 'count' => count($items)]);
    }

    public static function mark_synced($request) {
        global $wpdb;
        $params = $request->get_json_params();
        $ids = $params['ids'] ?? [];
        if (!empty($ids)) {
            $ids_str = implode(',', array_map('intval', $ids));
            $wpdb->query("UPDATE {$wpdb->prefix}esm_sync_log SET sync_status='synced', sync_timestamp=NOW() WHERE id IN ($ids_str)");
        }
        return rest_ensure_response(['marked' => count($ids)]);
    }

    public static function export_entity($request) {
        global $wpdb;
        $entity = sanitize_text_field($request['entity']);
        $table = self::table_map()[$entity] ?? null;
        if (!$table) return new WP_Error('unknown_entity', "Unknown: $entity", ['status' => 400]);
        $rows = $wpdb->get_results("SELECT * FROM {$wpdb->prefix}$table", ARRAY_A);
        return rest_ensure_response(['entity' => $entity, 'data' => $rows, 'count' => count($rows), 'version' => ESM_VERSION]);
    }

    public static function import_entity($request) {
        global $wpdb;
        $entity = sanitize_text_field($request['entity']);
        $params = $request->get_json_params();
        $records = $params['data'] ?? [];
        $table = self::table_map()[$entity] ?? null;
        if (!$table) return new WP_Error('unknown_entity', "Unknown: $entity", ['status' => 400]);
        $imported = 0; $errors = [];
        foreach ($records as $rec) {
            $sanitized = [];
            foreach ($rec as $k => $v) {
                $sanitized[sanitize_key($k)] = is_string($v) ? sanitize_text_field($v) : $v;
            }
            $inserted = $wpdb->replace("{$wpdb->prefix}$table", $sanitized);
            if ($inserted) $imported++; else $errors[] = $wpdb->last_error;
        }
        return rest_ensure_response(['imported' => $imported, 'errors' => $errors]);
    }

    public static function get_stats($request) {
        global $wpdb;
        $pfx = $wpdb->prefix;
        return rest_ensure_response([
            'total_students' => (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_students WHERE status='Active'"),
            'total_staff'    => (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_staff WHERE status='Active'"),
            'total_classes'  => (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_classes"),
            'total_invoices' => (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_invoices"),
            'fees_today'     => (float) $wpdb->get_var("SELECT COALESCE(SUM(amount),0) FROM {$pfx}esm_fee_payments WHERE payment_date=CURDATE()"),
            'fees_month'     => (float) $wpdb->get_var("SELECT COALESCE(SUM(amount),0) FROM {$pfx}esm_fee_payments WHERE YEAR(payment_date)=YEAR(CURDATE()) AND MONTH(payment_date)=MONTH(CURDATE())"),
            'pending_sync'   => (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_sync_log WHERE sync_status='pending'"),
            'version'        => ESM_VERSION,
            'author'         => ESM_AUTHOR,
        ]);
    }

    public static function fee_balance($request) {
        global $wpdb;
        $pfx = $wpdb->prefix;
        $student_id = intval($request['student_id']);
        $student = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$pfx}esm_students WHERE id=%d", $student_id));
        if (!$student) return new WP_Error('not_found', 'Student not found', ['status' => 404]);
        $level = $wpdb->get_var($wpdb->prepare("SELECT level FROM {$pfx}esm_classes WHERE id=%d", $student->class_id));
        $fl_name = ESM_Helpers::get_fee_level_name($level);
        $total_due = 0;
        if ($fl_name) {
            $fl = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$pfx}esm_fee_levels WHERE name=%s", $fl_name));
            if ($fl) $total_due = $fl->total;
        }
        $multiplier = ESM_Helpers::effective_fee_multiplier($student);
        $scholarship = $total_due * (1.0 - $multiplier);
        $net_due = $total_due * $multiplier;
        $paid = (float) $wpdb->get_var($wpdb->prepare("SELECT COALESCE(SUM(amount),0) FROM {$pfx}esm_fee_payments WHERE student_id=%d", $student_id));
        return rest_ensure_response([
            'student' => $student->first_name . ' ' . $student->last_name,
            'fee_classification' => $student->fee_classification,
            'total_due' => $total_due, 'scholarship_amount' => $scholarship,
            'net_due' => $net_due, 'total_paid' => $paid, 'balance' => $net_due - $paid,
        ]);
    }

    public static function class_level_info($request) {
        global $wpdb;
        $pfx = $wpdb->prefix;
        $class_id = intval($request['class_id']);
        $cls = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$pfx}esm_classes WHERE id=%d", $class_id));
        if (!$cls) return new WP_Error('not_found', 'Class not found', ['status' => 404]);
        $level = $cls->level ?? '';
        $fl_name = ESM_Helpers::get_fee_level_name($level);
        $fl = $fl_name ? $wpdb->get_row($wpdb->prepare("SELECT * FROM {$pfx}esm_fee_levels WHERE name=%s", $fl_name)) : null;
        return rest_ensure_response([
            'class_name' => $cls->name, 'level' => $level,
            'is_primary' => ESM_Helpers::is_primary_level($level),
            'fee_level_name' => $fl_name, 'fee_level_total' => $fl ? $fl->total : 0,
        ]);
    }

    private static function has_column($table, $column) {
        global $wpdb;
        static $cache = [];
        $key = $table . '.' . $column;
        if (!isset($cache[$key])) {
            $cache[$key] = (bool) $wpdb->get_var($wpdb->prepare(
                "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s AND column_name=%s",
                $table, $column
            ));
        }
        return $cache[$key];
    }
}
