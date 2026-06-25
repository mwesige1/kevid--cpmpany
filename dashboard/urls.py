from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [

    # ── Authentication ─────────────────────────────────
    # Custom login page for dashboard
    path(
        'login/',
        views.dashboard_login,
        name='login'
    ),
    # Logout and redirect to login
    path(
        'logout/',
        views.dashboard_logout,
        name='logout'
    ),

    # ── Overview ───────────────────────────────────────
    # Main dashboard home page
    path(
        '',
        views.overview,
        name='overview'
    ),

    # ── Sessions ───────────────────────────────────────
    # Active sessions with live countdown
    path(
        'sessions/',
        views.active_sessions,
        name='active_sessions'
    ),
    # Expired sessions history
    path(
        'sessions/expired/',
        views.expired_sessions,
        name='expired_sessions'
    ),
    # Manually disconnect a device
    path(
        'sessions/<int:session_id>/disconnect/',
        views.disconnect_session,
        name='disconnect_session'
    ),

    # ── Customers ──────────────────────────────────────
    # All registered customers
    path(
        'customers/',
        views.customers,
        name='customers'
    ),

    # Customer detail
    path(
        'customers/<int:device_id>/',
        views.customer_detail,
        name='customer_detail'
    ),

    # Delete customer
    path(
        'customers/<int:device_id>/delete/',
        views.customer_delete,
        name='customer_delete'
    ),
    

    # ── Devices ────────────────────────────────────────
    # All devices that have connected
    path(
        'devices/',
        views.devices,
        name='devices'
    ),
    # Block or unblock a device
    path(
        'devices/<int:device_id>/block/',
        views.block_device,
        name='block_device'
    ),

    # Router stats
    path(
        'routers/<int:router_id>/stats/',
        views.router_stats,
        name='router_stats'
    ),
    # Delete router
    path(
        'routers/<int:router_id>/delete/',
        views.delete_router,
        name='delete_router'
    ),
    # Provision router
    path(
        'routers/<int:router_id>/provision/',
        views.provision_router,
        name='provision_router'
    ),
    # Edit router
    path(
        'routers/<int:router_id>/edit/',
        views.edit_router,
        name='edit_router'
    ),

    # ── Packages ───────────────────────────────────────
    # All WiFi packages
    path(
        'packages/',
        views.packages,
        name='packages'
    ),
    # Create new package
    path(
        'packages/create/',
        views.create_package,
        name='create_package'
    ),
    # Toggle package status
    path(
        'packages/<int:package_id>/toggle/',
        views.toggle_package,
        name='toggle_package'
    ),

      # Delete a package permanently
    path(
        'packages/<int:package_id>/delete/',
        views.delete_package,
        name='delete_package'
    ),

    # Delete an expense
    path(
        'expenses/<int:expense_id>/delete/',
        views.delete_expense,
        name='delete_expense'
    ),

    # Delete advertisement
    path(
        'advertisements/<int:ad_id>/delete/',
        views.delete_advertisement,
        name='delete_advertisement'
    ),

    # Toggle advertisement active status
    path(
        'advertisements/<int:ad_id>/toggle/',
        views.toggle_advertisement,
        name='toggle_advertisement'
    ),

    # ── Payments ───────────────────────────────────────
    # All payment transactions
    path(
        'payments/',
        views.payments,
        name='payments'
    ),

    # ── Vouchers ───────────────────────────────────────
    # All voucher codes
    path(
        'vouchers/',
        views.vouchers,
        name='vouchers'
    ),
    # Generate new vouchers
    path(
        'vouchers/generate/',
        views.generate_vouchers,
        name='generate_vouchers'
    ),

    # ── Voucher Agents ─────────────────────────────────
    # All registered agents
    path(
        'agents/',
        views.voucher_agents,
        name='voucher_agents'
    ),
    # Create new agent
    path(
        'agents/create/',
        views.create_voucher_agent,
        name='create_voucher_agent'
    ),

    # Agent detail — stats and voucher list
    path(
        'agents/<int:agent_id>/',
        views.agent_detail,
        name='agent_detail'
    ),

    # ── Expenses ───────────────────────────────────────
    # All business expenses
    path(
        'expenses/',
        views.expenses,
        name='expenses'
    ),
    # Record new expense
    path(
        'expenses/create/',
        views.create_expense,
        name='create_expense'
    ),

    # Edit an expense
    path(
        'expenses/<int:expense_id>/edit/',
        views.edit_expense,
        name='edit_expense'
    ),

    # ── Withdrawals ────────────────────────────────────
    # All withdrawal requests
    path(
        'withdrawals/',
        views.withdrawals,
        name='withdrawals'
    ),
    # Create new withdrawal request
    path(
        'withdrawals/create/',
        views.create_withdrawal,
        name='create_withdrawal'
    ),
    # Update withdrawal status
    path(
        'withdrawals/<int:withdrawal_id>/update/',
        views.update_withdrawal_status,
        name='update_withdrawal_status'
    ),
    # Delete withdrawal
    path(
        'withdrawals/<int:withdrawal_id>/delete/',
        views.delete_withdrawal,
        name='delete_withdrawal'
    ),

    # ── Leads ──────────────────────────────────────────
    # All leads in pipeline
    path(
        'leads/',
        views.leads,
        name='leads'
    ),
    # Create new lead
    path(
        'leads/create/',
        views.create_lead,
        name='create_lead'
    ),
    # View lead detail
    path(
        'leads/<int:lead_id>/',
        views.lead_detail,
        name='lead_detail'
    ),
    # Delete lead
    path(
        'leads/<int:lead_id>/delete/',
        views.delete_lead,
        name='delete_lead'
    ),

    # ── Feedback ───────────────────────────────────────
    # All customer feedback
    path(
        'feedback/',
        views.feedback,
        name='feedback'
    ),

    # ── Equipment ──────────────────────────────────────
    # All physical assets
    path(
        'equipment/',
        views.equipment,
        name='equipment'
    ),
    # Record new equipment
    path(
        'equipment/create/',
        views.create_equipment,
        name='create_equipment'
    ),

    # Edit equipment
    path(
        'equipment/<int:equipment_id>/edit/',
        views.edit_equipment,
        name='edit_equipment'
    ),
    # Delete equipment
    path(
        'equipment/<int:equipment_id>/delete/',
        views.delete_equipment,
        name='delete_equipment'
    ),

    # ── Advertisements ─────────────────────────────────
    # All portal advertisements
    path(
        'advertisements/',
        views.advertisements,
        name='advertisements'
    ),
    # Create new advertisement
    path(
        'advertisements/create/',
        views.create_advertisement,
        name='create_advertisement'
    ),

    # Edit advertisement
    path(
        'advertisements/<int:ad_id>/edit/',
        views.edit_advertisement,
        name='edit_advertisement'
    ),

    # ── Messages ───────────────────────────────────────
    # All sent messages
    path(
        'messages/',
        views.messages,
        name='messages'
    ),
    # Send new message
    path(
        'messages/send/',
        views.send_message,
        name='send_message'
    ),

    # Delete message
    path(
        'messages/<int:message_id>/delete/',
        views.delete_message,
        name='delete_message'
    ),

    # ── MikroTik Routers ───────────────────────────────
    # All connected routers
    path(
        'routers/',
        views.routers,
        name='routers'
    ),
    # Add new router
    path(
        'routers/create/',
        views.create_router,
        name='create_router'
    ),

    # ── Financial Analytics ────────────────────────────
    # Full financial overview
    path(
        'analytics/',
        views.financial_analytics,
        name='financial_analytics'
    ),

    # ── Settings ───────────────────────────────────────
    # System settings
    path(
        'settings/',
        views.settings_view,
        name='settings'
    ),

    # ── Team Roles ─────────────────────────────────────
    path(
        'team-roles/',
        views.team_roles,
        name='team_roles'
    ),

    # ── Record Payment ─────────────────────────────────
    path(
        'payments/record/',
        views.record_payment,
        name='record_payment'
    ),

  
]