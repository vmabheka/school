<?php
/** Hostel — port of the offline app's templates/hostel/dashboard.html. */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;
$hostels = $wpdb->get_results("SELECT h.*, s.first_name AS warden_first, s.last_name AS warden_last FROM {$pfx}esm_hostels h LEFT JOIN {$pfx}esm_staff s ON s.id = h.warden_id");
$total_rooms = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_rooms");
$total_allocations = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_room_allocations WHERE status='Active'");
?>
<div class="page-header"><div><h1>Hostel Management</h1><p>Manage hostels, rooms, and allocations</p></div></div>

<div class="stats-grid">
    <div class="stat-card"><div class="icon blue"><i class="fas fa-building"></i></div><div class="info"><h3><?php echo esc_html(count($hostels)); ?></h3><p>Hostels</p></div></div>
    <div class="stat-card"><div class="icon green"><i class="fas fa-door-open"></i></div><div class="info"><h3><?php echo esc_html($total_rooms); ?></h3><p>Total Rooms</p></div></div>
    <div class="stat-card"><div class="icon yellow"><i class="fas fa-bed"></i></div><div class="info"><h3><?php echo esc_html($total_allocations); ?></h3><p>Active Allocations</p></div></div>
</div>

<?php if ($hostels): foreach ($hostels as $h):
    $rooms = $wpdb->get_results($wpdb->prepare("SELECT * FROM {$pfx}esm_rooms WHERE hostel_id=%d LIMIT 10", $h->id));
?>
<div class="card" style="margin-bottom:16px;">
    <div class="card-header"><h3><?php echo esc_html($h->name); ?> <span class="badge badge-info"><?php echo esc_html($h->gender); ?></span></h3></div>
    <div class="card-body">
        <p style="font-size:13px;"><strong>Capacity:</strong> <?php echo esc_html($h->capacity); ?> &nbsp; <strong>Warden:</strong> <?php echo esc_html($h->warden_first ? ($h->warden_first . ' ' . $h->warden_last) : 'Not assigned'); ?></p>
        <div class="table-container" style="margin-top:8px;">
            <table>
                <thead><tr><th>Room</th><th>Capacity</th><th>Occupancy</th><th>Available</th></tr></thead>
                <tbody>
                    <?php foreach ($rooms as $room): ?>
                    <tr>
                        <td><?php echo esc_html($room->room_number); ?></td>
                        <td><?php echo esc_html($room->capacity); ?></td>
                        <td><?php echo esc_html($room->current_occupancy); ?></td>
                        <td><span class="badge <?php echo $room->current_occupancy < $room->capacity ? 'badge-success' : 'badge-danger'; ?>"><?php echo esc_html($room->capacity - $room->current_occupancy); ?></span></td>
                    </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        </div>
    </div>
</div>
<?php endforeach; else: ?>
<div class="card"><div class="card-body empty-state"><i class="fas fa-bed"></i><h3>No hostels configured</h3></div></div>
<?php endif; ?>
