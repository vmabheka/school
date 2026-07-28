<?php
/**
 * ESM Sync Engine — bidirectional sync with the offline Flask app.
 *
 * Sync flow:
 *   1. PUSH: WordPress pending esm_sync_log rows -> Flask POST /api/sync
 *   2. PULL: Flask GET /api/sync/pending -> apply to WordPress tables
 *   3. CONFIRM: Flask POST /api/sync/mark-synced
 *   4. RESOLVE: newest_wins / wp_wins / flask_wins, same 3 strategies the
 *      offline app itself implements in its own /api/sync handler.
 *
 * All option names used here (esm_flask_endpoint, esm_sync_api_key, ...)
 * are consistent across this whole plugin — there is a single source of
 * truth, unlike the previous build which split them between esm_* and
 * ess_* and silently broke authentication.
 *
 * Author: Valentine T Mabheka | Version: 3.0.0
 */
if (!defined('ABSPATH')) exit;

class ESM_Sync_Engine {

    // Entity type -> WordPress table, mirrors the Flask app's own
    // entity_models map in its /api/sync handler (app.py).
    private static $entity_tables = [
        'Student'      => 'esm_students',
        'Staff'        => 'esm_staff',
        'FeePayment'   => 'esm_fee_payments',
        'ExamResult'   => 'esm_exam_results',
        'Notice'       => 'esm_notices',
        'FeeStructure' => 'esm_fee_structures',
        'FeeLevel'     => 'esm_fee_levels',
        'Class'        => 'esm_classes',
        'Subject'      => 'esm_subjects',
        'AcademicYear' => 'esm_academic_years',
        'Term'         => 'esm_terms',
        'Invoice'      => 'esm_invoices',
    ];

    // Entities exposed via /api/export/<entity> and /api/import/<entity>
    // on both sides — mirrors app.py's api_export_entity() entity_map,
    // plus invoices/invoice_items which the offline app also has but the
    // previous plugin build never wired up.
    public static $exportable_entities = [
        'academic_years', 'terms', 'classes', 'subjects', 'fee_levels',
        'fee_structures', 'students', 'staff', 'fee_payments',
        'invoices', 'invoice_items', 'exam_results', 'notices',
    ];

    public static function run_sync() {
        $push_result = self::push_all_pending();
        $pull_result = self::pull_from_flask();
        update_option('esm_last_sync_time', current_time('mysql'));
        update_option('esm_last_sync_status', 'success');
        return ['push' => $push_result, 'pull' => $pull_result, 'timestamp' => current_time('mysql')];
    }

    public static function push_all_pending() {
        global $wpdb;
        $pfx = $wpdb->prefix;
        $endpoint = get_option('esm_flask_endpoint', '');
        $api_key  = get_option('esm_sync_api_key', '');

        if (!$endpoint) return ['error' => 'Flask endpoint not configured'];

        $pending = $wpdb->get_results("SELECT * FROM {$pfx}esm_sync_log WHERE sync_status='pending' ORDER BY created_at ASC LIMIT 500");
        if (empty($pending)) return ['pushed' => 0, 'message' => 'No pending changes'];

        $success = 0; $failed = 0;

        foreach ($pending as $log) {
            $data = json_decode($log->data_snapshot, true);
            if (($log->action === 'CREATE' || $log->action === 'UPDATE') && isset(self::$entity_tables[$log->entity_type])) {
                $table = $pfx . self::$entity_tables[$log->entity_type];
                $record = $wpdb->get_row($wpdb->prepare("SELECT * FROM $table WHERE id=%d", $log->entity_id), ARRAY_A);
                if ($record) {
                    $data = $record;
                }
            }

            $payload = [
                'entity_type' => $log->entity_type,
                'entity_id'   => $log->entity_id,
                'action'      => $log->action,
                'data'        => $data,
                'sync_id'     => $data['sync_id'] ?? '',
                'api_key'     => $api_key,
                'source'      => 'wordpress',
                'timestamp'   => current_time('mysql'),
                'conflict_strategy' => get_option('esm_conflict_strategy', 'newest_wins'),
            ];

            $response = wp_remote_post(rtrim($endpoint, '/') . '/api/sync', [
                'timeout' => 15,
                'headers' => ['Content-Type' => 'application/json', 'X-ESM-API-Key' => $api_key],
                'body'    => wp_json_encode($payload),
            ]);

            if (is_wp_error($response)) {
                $failed++;
                $wpdb->update("{$pfx}esm_sync_log", ['sync_status' => 'failed', 'sync_timestamp' => current_time('mysql')], ['id' => $log->id]);
                continue;
            }
            $code = wp_remote_retrieve_response_code($response);
            if ($code >= 200 && $code < 300) {
                $success++;
                $wpdb->update("{$pfx}esm_sync_log", ['sync_status' => 'synced', 'sync_timestamp' => current_time('mysql')], ['id' => $log->id]);
            } else {
                $failed++;
                $wpdb->update("{$pfx}esm_sync_log", ['sync_status' => 'failed', 'sync_timestamp' => current_time('mysql')], ['id' => $log->id]);
            }
        }

        return ['pushed' => $success, 'failed' => $failed, 'total' => count($pending)];
    }

    public static function pull_from_flask() {
        global $wpdb;
        $pfx = $wpdb->prefix;
        $endpoint = get_option('esm_flask_endpoint', '');
        $api_key  = get_option('esm_sync_api_key', '');
        $conflict_strategy = get_option('esm_conflict_strategy', 'newest_wins');

        if (!$endpoint) return ['error' => 'Flask endpoint not configured'];

        $response = wp_remote_get(rtrim($endpoint, '/') . '/api/sync/pending', [
            'timeout' => 30, 'headers' => ['X-ESM-API-Key' => $api_key],
        ]);

        if (is_wp_error($response)) {
            update_option('esm_last_sync_status', 'connection_failed');
            return ['error' => $response->get_error_message()];
        }

        $body = json_decode(wp_remote_retrieve_body($response), true);
        $items = $body['pending'] ?? [];
        if (empty($items)) return ['pulled' => 0, 'message' => 'No pending changes from Flask'];

        $applied = 0; $conflicts = 0; $skipped = 0; $synced_flask_ids = [];

        foreach ($items as $item) {
            $entity_type = $item['entity_type'];
            $action = $item['action'];
            $data = $item['data'] ?? [];
            $incoming_timestamp = $item['created_at'] ?? '';

            if (!isset(self::$entity_tables[$entity_type])) { $synced_flask_ids[] = $item['id']; continue; }
            $table = $pfx . self::$entity_tables[$entity_type];

            if ($action === 'CREATE' || $action === 'UPDATE') {
                $sync_id = $data['sync_id'] ?? '';
                $exists = $sync_id ? $wpdb->get_var($wpdb->prepare("SELECT id FROM $table WHERE sync_id=%s", $sync_id)) : null;

                if ($exists) {
                    $conflicts += ($action === 'CREATE') ? 1 : 0;
                    $should_update = true;
                    if ($conflict_strategy === 'newest_wins' && $incoming_timestamp) {
                        $should_update = self::should_update_record($table, $exists, $incoming_timestamp);
                    } elseif ($conflict_strategy === 'wp_wins') {
                        $should_update = false;
                    }
                    if ($should_update) {
                        self::update_record($table, $data, $exists);
                        $applied++;
                    } else {
                        $skipped++;
                    }
                } else {
                    self::insert_record($table, $data);
                    $applied++;
                }
            } elseif ($action === 'DELETE') {
                $entity_id = $item['entity_id'] ?? 0;
                if ($entity_id && in_array($entity_type, ['Student', 'Staff'], true)) {
                    $wpdb->update($table, ['status' => 'Inactive'], ['id' => $entity_id]);
                } elseif ($entity_id) {
                    $wpdb->delete($table, ['id' => $entity_id]);
                }
                $applied++;
            }
            $synced_flask_ids[] = $item['id'];
        }

        if (!empty($synced_flask_ids)) {
            wp_remote_post(rtrim($endpoint, '/') . '/api/sync/mark-synced', [
                'timeout' => 15,
                'headers' => ['Content-Type' => 'application/json', 'X-ESM-API-Key' => $api_key],
                'body'    => wp_json_encode(['ids' => $synced_flask_ids, 'api_key' => $api_key]),
            ]);
        }

        return ['pulled' => $applied, 'conflicts' => $conflicts, 'skipped' => $skipped, 'total' => count($items)];
    }

    /**
     * Full export — dump all WordPress-side data (used to seed a brand
     * new Flask install, or for backups).
     */
    public static function full_export() {
        global $wpdb;
        $pfx = $wpdb->prefix;
        $export = ['version' => ESM_VERSION, 'author' => ESM_AUTHOR, 'exported_at' => current_time('mysql')];
        foreach (self::$exportable_entities as $entity) {
            $table = $pfx . 'esm_' . $entity;
            $rows = $wpdb->get_results("SELECT * FROM $table", ARRAY_A);
            $export['data'][$entity] = $rows ?: [];
        }
        return $export;
    }

    /**
     * Full import — pull every entity (including invoices/invoice_items,
     * which the previous plugin build could not import at all) from the
     * Flask app's /api/export/<entity> endpoints into WordPress.
     */
    public static function full_import($entities = []) {
        global $wpdb;
        $pfx = $wpdb->prefix;
        $endpoint = get_option('esm_flask_endpoint', '');
        $api_key  = get_option('esm_sync_api_key', '');
        if (!$endpoint) return ['error' => 'Flask endpoint not configured'];
        if (empty($entities)) $entities = self::$exportable_entities;

        $results = [];
        foreach ($entities as $entity) {
            $response = wp_remote_get(rtrim($endpoint, '/') . '/api/export/' . $entity, [
                'timeout' => 60, 'headers' => ['X-ESM-API-Key' => $api_key],
            ]);
            if (is_wp_error($response)) {
                $results[$entity] = ['error' => $response->get_error_message()];
                continue;
            }
            $code = wp_remote_retrieve_response_code($response);
            if ($code >= 400) {
                $results[$entity] = ['error' => "HTTP $code"];
                continue;
            }
            $body = json_decode(wp_remote_retrieve_body($response), true);
            $records = $body['data'] ?? [];
            $table = $pfx . 'esm_' . $entity;
            $imported = 0;
            foreach ($records as $rec) {
                $sanitized = [];
                foreach ($rec as $k => $v) {
                    $sanitized[sanitize_key($k)] = is_string($v) ? $v : $v;
                }
                if (isset($sanitized['sync_id']) && $sanitized['sync_id']) {
                    $exists = $wpdb->get_var($wpdb->prepare("SELECT id FROM $table WHERE sync_id=%s", $sanitized['sync_id']));
                    if ($exists) {
                        $id_to_keep = $sanitized['id'] ?? null;
                        unset($sanitized['id']);
                        $wpdb->update($table, $sanitized, ['id' => $exists]);
                    } else {
                        // Preserve the Flask-side numeric ID so that
                        // foreign keys (class_id, student_id, invoice_id,
                        // etc.) referenced by *other* imported entities
                        // continue to resolve correctly.
                        $wpdb->insert($table, $sanitized);
                    }
                } else {
                    // No sync_id (e.g. esm_invoice_items) — preserve
                    // the source ID directly so invoice_id FKs still work.
                    $wpdb->replace($table, $sanitized);
                }
                $imported++;
            }
            $results[$entity] = ['imported' => $imported];
        }
        return $results;
    }

    /**
     * Test connectivity to the Flask app. Uses /api/sync/pending rather
     * than /api/stats — the offline app's own /api/stats route requires
     * an interactive login session (not just the API key), so it always
     * fails here; /api/sync/pending is authenticated purely by
     * X-ESM-API-Key, matching how this plugin actually talks to Flask.
     */
    public static function test_connection($endpoint, $api_key) {
        $response = wp_remote_get(rtrim($endpoint, '/') . '/api/sync/pending', [
            'timeout' => 10, 'headers' => ['X-ESM-API-Key' => $api_key],
        ]);
        if (is_wp_error($response)) {
            return ['success' => false, 'error' => $response->get_error_message()];
        }
        $code = wp_remote_retrieve_response_code($response);
        $body = json_decode(wp_remote_retrieve_body($response), true);
        if ($code >= 200 && $code < 300 && is_array($body)) {
            return [
                'success' => true, 'status_code' => $code,
                'flask_pending_sync' => $body['count'] ?? 0,
            ];
        }
        return ['success' => false, 'status_code' => $code, 'error' => 'Connection failed'];
    }

    // ─── Private helpers ───────────────────────────────────────────────

    private static function insert_record($table, $data) {
        global $wpdb;
        $sanitized = [];
        foreach ($data as $k => $v) {
            $sanitized[sanitize_key($k)] = is_string($v) ? sanitize_text_field($v) : $v;
        }
        unset($sanitized['id']);
        if (!isset($sanitized['created_at']) && self::table_has_column($table, 'created_at')) {
            $sanitized['created_at'] = current_time('mysql');
        }
        $wpdb->insert($table, $sanitized);
    }

    private static function update_record($table, $data, $id) {
        global $wpdb;
        $sanitized = [];
        foreach ($data as $k => $v) {
            $sanitized[sanitize_key($k)] = is_string($v) ? sanitize_text_field($v) : $v;
        }
        unset($sanitized['id']);
        if (self::table_has_column($table, 'updated_at')) {
            $sanitized['updated_at'] = current_time('mysql');
        }
        $wpdb->update($table, $sanitized, ['id' => $id]);
    }

    private static function table_has_column($table, $column) {
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

    /**
     * Timestamp-based conflict resolution, normalized to UTC (WordPress
     * stores local time via current_time('mysql'), Flask stores UTC).
     */
    private static function should_update_record($table, $existing_id, $incoming_timestamp) {
        global $wpdb;
        if (empty($incoming_timestamp)) return true;
        $existing_updated = self::table_has_column($table, 'updated_at')
            ? $wpdb->get_var($wpdb->prepare("SELECT updated_at FROM $table WHERE id=%d", $existing_id))
            : null;
        if (empty($existing_updated)) return true;

        $existing_dt = self::normalize_to_utc($existing_updated);
        $incoming_dt = self::normalize_to_utc($incoming_timestamp);
        if ($existing_dt === false || $incoming_dt === false) return true;
        return $incoming_dt > $existing_dt;
    }

    private static function normalize_to_utc($timestamp_str) {
        if (empty($timestamp_str)) return false;
        try {
            if (preg_match('/[+-]\d{2}:\d{2}$/', $timestamp_str) || substr($timestamp_str, -1) === 'Z') {
                $dt = new DateTime($timestamp_str);
                $dt->setTimezone(new DateTimeZone('UTC'));
                return $dt->getTimestamp();
            }
            $tz_string = get_option('timezone_string', 'UTC');
            $dt = $tz_string ? new DateTime($timestamp_str, new DateTimeZone($tz_string))
                              : new DateTime($timestamp_str, new DateTimeZone('UTC'));
            $dt->setTimezone(new DateTimeZone('UTC'));
            return $dt->getTimestamp();
        } catch (Exception $e) {
            return strtotime($timestamp_str);
        }
    }
}

    /**
     * New: Test handshake with Flask offline app
     */
    public static function handshake($endpoint, $api_key = '') {
        $url = rtrim($endpoint, '/') . '/api/sync/handshake';
        
        $response = wp_remote_get($url, [
            'timeout' => 10,
            'headers' => ['X-ESM-API-Key' => $api_key]
        ]);

        if (is_wp_error($response)) {
            return ['success' => false, 'error' => $response->get_error_message()];
        }

        $body = json_decode(wp_remote_retrieve_body($response), true);
        
        return [
            'success' => true,
            'flask_version' => $body['version'] ?? 'unknown',
            'school_name'   => $body['school_name'] ?? '',
            'school_motto'  => $body['school_motto'] ?? '',
            'timestamp'     => $body['timestamp'] ?? ''
        ];
    }
