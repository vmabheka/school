<?php
/**
 * Fee Levels — port of the offline app's templates/fees/levels.html,
 * including the development_levy / registration_fee / textbook_levy
 * columns the previous plugin build's fee-level table was missing.
 */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;
$levels = $wpdb->get_results("SELECT * FROM {$pfx}esm_fee_levels ORDER BY total ASC");
?>
<div class="page-header">
    <div><h1>Fee Levels</h1><p>Default fee amounts per level: ECD, Junior (Grade 1&ndash;7), O Level (Form 1&ndash;4), A Level (Form 5&ndash;6)</p></div>
    <div class="actions"><a href="<?php echo esc_url(home_url('/sms/fees/')); ?>" class="btn btn-secondary"><i class="fas fa-arrow-left"></i> Back to Fees</a></div>
</div>

<div class="stats-grid">
    <?php foreach ($levels as $fl): ?>
    <div class="stat-card">
        <div class="icon green"><i class="fas fa-layer-group"></i></div>
        <div class="info">
            <h3><?php echo esc_html($fl->name); ?></h3>
            <p><?php echo esc_html($fl->description ?: ''); ?></p>
            <p style="margin-top:4px;"><strong>$<?php echo esc_html(number_format($fl->total, 2)); ?></strong> / term recurring</p>
        </div>
    </div>
    <?php endforeach; ?>
</div>

<div class="card">
    <div class="card-header"><h3>Fee Levels Breakdown</h3></div>
    <div class="table-container">
        <table>
            <thead><tr><th>Level</th><th>Code</th><th>Description</th><th>Tuition (Term)</th><th>Dev Levy (Term)</th><th>Reg Fee (Once-off)</th><th>Textbook Levy (Once-off)</th><th>Term Total</th></tr></thead>
            <tbody>
                <?php foreach ($levels as $fl): ?>
                <tr>
                    <td><strong><?php echo esc_html($fl->name); ?></strong></td>
                    <td><span class="badge badge-info"><?php echo esc_html($fl->code); ?></span></td>
                    <td><?php echo esc_html($fl->description ?: '-'); ?></td>
                    <td style="color:var(--primary);font-weight:bold;">$<?php echo esc_html(number_format($fl->tuition, 2)); ?></td>
                    <td>$<?php echo esc_html(number_format($fl->development_levy, 2)); ?></td>
                    <td>$<?php echo esc_html(number_format($fl->registration_fee, 2)); ?></td>
                    <td>$<?php echo esc_html(number_format($fl->textbook_levy, 2)); ?></td>
                    <td><strong>$<?php echo esc_html(number_format($fl->total, 2)); ?></strong></td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</div>
