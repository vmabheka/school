<?php if (!defined('ABSPATH')) exit; ?>
    </main>
    <script>
        document.addEventListener('click', function (e) {
            if (!e.target.closest('.user-dropdown')) {
                var d = document.getElementById('userDropdown');
                if (d) d.classList.remove('show');
            }
        });
        document.addEventListener('click', function (e) {
            var sidebar = document.getElementById('sidebar');
            if (sidebar && sidebar.classList.contains('open') && !e.target.closest('.sidebar') && !e.target.closest('.menu-toggle')) {
                sidebar.classList.remove('open');
            }
        });
    </script>
</body>
</html>
