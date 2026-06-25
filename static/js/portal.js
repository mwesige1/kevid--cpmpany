// ── State ──────────────────────────────────────────────
let state = {
    packageId   : null,
    packageName : '',
    price       : 0,
    duration    : '',
    provider    : null,
    isFree      : false,
};

let pollingInterval = null;
let currentOrderId  = null;

// ── Tab Switching ──────────────────────────────────────
function switchTab(tab) {
    const isPay = tab === 'pay';
    document.getElementById('tab-pay').style.display     =
        isPay ? 'block' : 'none';
    document.getElementById('tab-voucher').style.display =
        isPay ? 'none' : 'block';

    const payBtn     = document.getElementById('tab-btn-pay');
    const voucherBtn = document.getElementById('tab-btn-voucher');

    if (isPay) {
        payBtn.style.background     = '#fff';
        payBtn.style.color          = '#2563eb';
        payBtn.style.boxShadow      = '0 1px 4px rgba(0,0,0,0.1)';
        voucherBtn.style.background = 'none';
        voucherBtn.style.color      = '#64748b';
        voucherBtn.style.boxShadow  = 'none';
    } else {
        voucherBtn.style.background = '#fff';
        voucherBtn.style.color      = '#2563eb';
        voucherBtn.style.boxShadow  = '0 1px 4px rgba(0,0,0,0.1)';
        payBtn.style.background     = 'none';
        payBtn.style.color          = '#64748b';
        payBtn.style.boxShadow      = 'none';
    }
}

// ── Select Plan ────────────────────────────────────────
function selectPlan(el) {
    while (el && !el.classList.contains('plan')) {
        el = el.parentElement;
    }
    if (!el) return;

    document.querySelectorAll('.plan').forEach(p => p.classList.remove('sel'));
    el.classList.add('sel');

    state.packageId   = el.dataset.packageId;
    state.packageName = el.dataset.packageName;
    state.price       = parseInt(el.dataset.packagePrice);
    state.duration    = el.dataset.packageDuration.trim();
    state.isFree      = el.dataset.isFree === 'true';

    document.getElementById('selected-package-id').value       = state.packageId;
    document.getElementById('selected-package-name').value     = state.packageName;
    document.getElementById('selected-package-price').value    = state.price;
    document.getElementById('selected-package-duration').value = state.duration;
    document.getElementById('selected-is-free').value          = state.isFree;

    validate();
}

// ── Select Method ──────────────────────────────────────
function selectMethod(el) {
    while (el && !el.classList.contains('method')) {
        el = el.parentElement;
    }
    if (!el) return;

    document.querySelectorAll('.method').forEach(m => m.classList.remove('sel'));
    el.classList.add('sel');

    state.provider = el.dataset.method;
    document.getElementById('selected-provider').value = state.provider;

    validate();
}

// ── Validate & Update Button ───────────────────────────
function validate() {
    const phone = document.getElementById('phone-number')
                  ? document.getElementById('phone-number').value
                  : '';
    const btn = document.getElementById('pay-btn');
    const sum = document.getElementById('sum-value');

    if (state.isFree) {
        sum.textContent = 'FREE';
        btn.disabled    = !state.packageId;
        btn.textContent = state.packageId
            ? '🎁 Activate Free Trial'
            : 'Select a plan to continue';
        return;
    }

    sum.textContent = state.price
        ? 'UGX ' + state.price.toLocaleString()
        : '—';

    if (state.packageId && state.provider && phone.length === 9) {
        btn.disabled    = false;
        btn.textContent = 'Pay UGX ' + state.price.toLocaleString();
    } else {
        btn.disabled = true;
        if (!state.packageId)     btn.textContent = 'Select a plan to continue';
        else if (!state.provider) btn.textContent = 'Select a payment method';
        else                      btn.textContent = 'Enter a valid number';
    }
}

// ── Open Modal ─────────────────────────────────────────
function openModal(status, title, msg, rows = []) {
    const icon = document.getElementById('modal-icon');

    document.getElementById('modal-status').className  = 'modal-status ' + status;
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-msg').textContent   = msg;

    if (status === 'processing') {
        icon.className = 'bi bi-hourglass-split';
    } else if (status === 'success') {
        icon.className = 'bi bi-check-circle-fill';
    } else {
        icon.className = 'bi bi-x-circle-fill';
    }

    // Build detail rows
    const rowsEl = document.getElementById('modal-rows');
    rowsEl.innerHTML = rows.map(r =>
        `<div class="modal-row">
            <span>${r.label}</span>
            <span>${r.value}</span>
        </div>`
    ).join('');

    document.getElementById('modal').classList.add('open');
}

// ── Close Modal ────────────────────────────────────────
function closeModal() {
    document.getElementById('modal').classList.remove('open');
    if (pollingInterval) clearInterval(pollingInterval);
}

// ── Initiate Payment ───────────────────────────────────
function initiatePayment() {
    const phone    = document.getElementById('phone-number').value;
    const mac      = document.getElementById('device-mac').value;
    const provider = state.provider === 'mtn' ? 'MTN MoMo' : 'Airtel Money';

    openModal('processing', 'Processing payment',
        'Check your phone and enter your PIN to confirm', [
        ['Network', provider],
        ['Number',  '+256 ' + phone],
        ['Plan',    state.packageName + ' · ' + state.duration],
        ['Amount',  state.isFree ? 'FREE' : 'UGX ' + state.price.toLocaleString()]
    ].map(([l, v]) => ({ label: l, value: v })));

    document.getElementById('pay-btn').disabled = true;

    fetch('/payments/initiate/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            package_id:   state.packageId,
            phone_number: '0' + phone,
            provider:     state.provider,
            mac_address:  mac,
            is_free:      state.isFree,
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'pending') {
            currentOrderId = data.order_id;
            pollPaymentStatus();
        } else {
            openModal('error', 'Payment failed',
                data.message || 'Could not initiate payment. Please try again.');
            document.getElementById('pay-btn').disabled = false;
        }
    })
    .catch(() => {
        openModal('error', 'Network error',
            'Something went wrong. Please try again.');
        document.getElementById('pay-btn').disabled = false;
    });
}

// ── Poll Payment Status ────────────────────────────────
function pollPaymentStatus() {
    pollingInterval = setInterval(() => {
        fetch('/payments/status/' + currentOrderId + '/')
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                clearInterval(pollingInterval);
                openModal('success', 'Payment confirmed',
                    "You're connected! Enjoy your browsing.");
                setTimeout(() => {
                    window.location.href = '/connected/';
                }, 2500);
            } else if (data.status === 'failed') {
                clearInterval(pollingInterval);
                openModal('error', 'Payment failed',
                    'Your payment was not completed. Please try again.');
                document.getElementById('pay-btn').disabled = false;
            }
        });
    }, 3000);

    // Stop after 2 minutes
    setTimeout(() => {
        if (pollingInterval) {
            clearInterval(pollingInterval);
            openModal('error', 'Timed out',
                'No response received. Please try again.');
            document.getElementById('pay-btn').disabled = false;
        }
    }, 120000);
}

// ── Voucher Code Formatter ─────────────────────────────
function formatVoucher(input) {
    let val = input.value.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
    if (val.length > 4)  val = val.slice(0,4) + '-' + val.slice(4);
    if (val.length > 9)  val = val.slice(0,9) + '-' + val.slice(9);
    if (val.length > 14) val = val.slice(0,14) + '-' + val.slice(14);
    input.value = val;
}

// ── Get CSRF Cookie ────────────────────────────────────
function getCookie(name) {
    let val = null;
    if (document.cookie) {
        document.cookie.split(';').forEach(c => {
            c = c.trim();
            if (c.startsWith(name + '='))
                val = decodeURIComponent(c.slice(name.length + 1));
        });
    }
    return val;
}