/**
 * Excel Schools Management - Admin JavaScript
 * Version: 2.0.0 | Author: Valentine T Mabheka
 */
(function($) {
    'use strict';

    // Level → Class cascade
    var levelClasses = {};
    var feeLevels = {};

    function initLevelClassCascade() {
        var levelSelect = $('#esm-level-select');
        var classSelect = $('#esm-class-select');
        if (!levelSelect.length || !classSelect.length) return;

        // Load level-classes map from server
        $.post(esm_ajax.ajax_url, {
            action: 'esm_get_level_classes_data',
            nonce: esm_ajax.nonce
        }, function(resp) {
            if (resp.success) {
                levelClasses = resp.data.level_classes;
                feeLevels = resp.data.fee_levels;
            }
        });

        levelSelect.on('change', function() {
            var level = $(this).val();
            classSelect.html('<option value="">Select Class</option>');
            if (level && levelClasses[level]) {
                levelClasses[level].forEach(function(c) {
                    classSelect.append('<option value="' + c.id + '">' + c.name + '</option>');
                });
            }
            // Show fee level info
            var flName = getFeeLevelName(level);
            var flInfo = $('#esm-fee-level-info');
            if (flName && feeLevels[flName]) {
                flInfo.html(flName + ' — $' + feeLevels[flName].toFixed(2) + '/term').show();
            } else {
                flInfo.hide();
            }
            // Show primary subjects info
            var psInfo = $('#esm-primary-subjects-info');
            if (isPrimaryLevel(level)) { psInfo.show(); } else { psInfo.hide(); }
        });
    }

    function getFeeLevelName(level) {
        if (!level) return null;
        var lvl = level.trim().toLowerCase();
        if (lvl.indexOf('ecd') === 0) return 'ECD';
        var gm = lvl.match(/grade\s*(\d+)/);
        if (gm && parseInt(gm[1]) >= 1 && parseInt(gm[1]) <= 7) return 'Junior';
        var fm = lvl.match(/form\s*(\d+)/);
        if (fm) { var f = parseInt(fm[1]); if (f <= 4) return 'O Level'; if (f >= 5) return 'A Level'; }
        return null;
    }

    function isPrimaryLevel(level) {
        if (!level) return false;
        var lvl = level.trim().toLowerCase();
        if (lvl.indexOf('ecd') === 0) return true;
        var gm = lvl.match(/grade\s*(\d+)/);
        if (gm && parseInt(gm[1]) >= 1 && parseInt(gm[1]) <= 7) return true;
        return false;
    }

    // Scholarship fields toggle
    function initScholarshipToggle() {
        var fc = $('#esm-fee-classification');
        if (!fc.length) return;
        function update() {
            var val = fc.val();
            var isScholarship = val !== 'Regular';
            $('#esm-scholarship-type-group').toggle(isScholarship);
            $('#esm-scholarship-sponsor-group').toggle(isScholarship);
            $('#esm-scholarship-notes-group').toggle(isScholarship);
            $('#esm-staff-link-group').toggle(val === 'Staff Scholarship');
            if (val === 'Orphan') {
                $('#esm-scholarship-type').val('Full');
                $('#esm-scholarship-percentage').val('100');
            }
            updatePctVisibility();
        }
        function updatePctVisibility() {
            var type = $('#esm-scholarship-type').val();
            $('#esm-scholarship-percentage-group').toggle(type === 'Partial');
        }
        fc.on('change', update);
        $('#esm-scholarship-type').on('change', updatePctVisibility);
        update();
    }

    // Bulk import file upload
    function initBulkImport() {
        var form = $('#esm-bulk-import-form');
        if (!form.length) return;
        form.on('submit', function(e) {
            e.preventDefault();
            var formData = new FormData(this);
            formData.append('action', form.data('action'));
            formData.append('nonce', esm_ajax.nonce);
            $.ajax({
                url: esm_ajax.ajax_url,
                data: formData,
                processData: false,
                contentType: false,
                type: 'POST',
                success: function(resp) {
                    if (resp.success) {
                        alert('Imported ' + resp.data.created + ' records.');
                    } else {
                        alert('Error: ' + resp.data);
                    }
                }
            });
        });
    }

    // Fee balance check
    function initFeeBalance() {
        var btn = $('#esm-check-balance-btn');
        if (!btn.length) return;
        btn.on('click', function() {
            var studentId = $('#esm-student-id').val();
            $.get(esm_ajax.ajax_url, {
                action: 'esm_get_fee_balance',
                nonce: esm_ajax.nonce,
                student_id: studentId
            }, function(resp) {
                if (resp.success) {
                    var d = resp.data;
                    var html = '<div class="esm-card"><div class="esm-card-body">';
                    html += '<h3>Fee Balance: ' + d.student + '</h3>';
                    html += '<p>Classification: ' + d.fee_classification + '</p>';
                    html += '<p>Total Due: $' + d.total_due.toFixed(2) + '</p>';
                    html += '<p>Scholarship: $' + d.scholarship_amount.toFixed(2) + '</p>';
                    html += '<p>Net Due: $' + d.net_due.toFixed(2) + '</p>';
                    html += '<p>Paid: $' + d.total_paid.toFixed(2) + '</p>';
                    html += '<p><strong>Balance: $' + d.balance.toFixed(2) + '</strong></p>';
                    html += '</div></div>';
                    $('#esm-balance-result').html(html);
                }
            });
        });
    }

    // Init on DOM ready
    $(document).ready(function() {
        initLevelClassCascade();
        initScholarshipToggle();
        initBulkImport();
        initFeeBalance();
    });

})(jQuery);
