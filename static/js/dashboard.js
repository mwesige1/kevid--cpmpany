/* ============================================
   KEVID TECH DASHBOARD — dashboard.js
   Handles: sidebar toggle, modals, confirmations
   Used by: templates/dashboard/base.html
   ============================================ */

/* ── Sidebar Toggle ───────────────────────── */
(function() {
    var sidebar  = document.getElementById('sidebar');
    var overlay  = document.getElementById('sidebarOverlay');
    var openBtn  = document.getElementById('hamburger');
    var closeBtn = document.getElementById('sidebarClose');

    function open() {
        sidebar.classList.add('open');
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function close() {
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    openBtn.addEventListener('click', open);
    closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', close);

    /* Close sidebar when a nav link is tapped on mobile */
    sidebar.querySelectorAll('.nav-item').forEach(function(link) {
        link.addEventListener('click', function() {
            if (window.innerWidth < 769) close();
        });
    });
})();