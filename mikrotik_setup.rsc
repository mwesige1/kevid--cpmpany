# ═══════════════════════════════════════════════════════════════
# Optimum WiFi Portal — MikroTik Auto-Provisioning Script
# RouterOS 7.x — Requires device-mode: advanced
# Paste this into System > Scripts as a NEW script, then run it
# with: /system script run optimum-setup
# ═══════════════════════════════════════════════════════════════

# ── EDIT THESE TWO LINES ONLY ──────────────────────────────────
:local routerIdentityRaw "kabalagala"
:local routerLocation    "kabalagala"
# ═══════════════════════════════════════════════════════════════

# ── FIXED SETTINGS — DO NOT CHANGE ─────────────────────────────
:local portalDomain     "optimuminnovationhotspot.com"
:local lanIP            "192.168.88.1"
:local lanNetwork       "192.168.88.0/24"
:local poolStart        "192.168.88.2"
:local poolEnd          "192.168.88.254"
# ═══════════════════════════════════════════════════════════════

# ── Auto-sanitize identity: replace spaces with hyphens ────────
# URLs cannot contain spaces — this prevents the 400 error
:local routerIdentity ""
:local i 0
:while ($i < [:len $routerIdentityRaw]) do={
    :local ch [:pick $routerIdentityRaw $i ($i+1)]
    :if ($ch = " ") do={
        :set routerIdentity ($routerIdentity . "-")
    } else={
        :set routerIdentity ($routerIdentity . $ch)
    }
    :set i ($i + 1)
}

:put ""
:put "═══════════════════════════════════════════════"
:put "  Optimum WiFi — Auto Configuration"
:put "═══════════════════════════════════════════════"
:put ("  Router  : " . $routerIdentity)
:put ("  Location: " . $routerLocation)
:put "═══════════════════════════════════════════════"
:put ""

# ── STEP 1 — Router identity ───────────────────────────────────
:put "Step 1: Setting router identity..."
/system identity set name=$routerIdentity
:put ("  ✅ Identity: " . $routerIdentity)

# ── STEP 2 — Bridge ───────────────────────────────────────────
:put "Step 2: Configuring LAN bridge..."
:if ([:len [/interface bridge find name="bridge1"]] = 0) do={
    /interface bridge add name=bridge1 protocol-mode=rstp
}
:foreach port in={"ether2";"ether3";"ether4";"ether5"} do={
    :if ([:len [/interface bridge port find interface=$port bridge=bridge1]] = 0) do={
        :do { /interface bridge port add interface=$port bridge=bridge1 } on-error={}
    }
}
:if ([:len [/ip address find interface="bridge1"]] = 0) do={
    /ip address add address=($lanIP . "/24") interface=bridge1
}
:put "  ✅ Bridge configured"

# ── STEP 3 — WAN DHCP Client on ether1 ─────────────────────────
:put "Step 3: Configuring WAN (ether1) DHCP client..."
:if ([:len [/ip dhcp-client find interface="ether1"]] = 0) do={
    /ip dhcp-client add interface=ether1 disabled=no use-peer-dns=yes add-default-route=yes
} else={
    /ip dhcp-client set [find interface="ether1"] disabled=no
}
:put "  ✅ ether1 set to obtain internet via DHCP"

# ── STEP 4 — DHCP Server (LAN) ─────────────────────────────────
:put "Step 4: Configuring DHCP server..."
:if ([:len [/ip pool find name="dhcp_pool0"]] = 0) do={
    /ip pool add name=dhcp_pool0 ranges=($poolStart . "-" . $poolEnd)
}
:if ([:len [/ip dhcp-server find name="dhcp1"]] = 0) do={
    /ip dhcp-server add name=dhcp1 interface=bridge1 \
        address-pool=dhcp_pool0 lease-time=1h disabled=no
}
:if ([:len [/ip dhcp-server network find address=$lanNetwork]] = 0) do={
    /ip dhcp-server network add address=$lanNetwork \
        gateway=$lanIP dns-server=$lanIP
} else={
    /ip dhcp-server network set [find address=$lanNetwork] \
        gateway=$lanIP dns-server=$lanIP
}
:put "  ✅ DHCP configured — DNS server: router itself"

# ── STEP 5 — NAT ──────────────────────────────────────────────
:put "Step 5: Configuring NAT..."
:if ([:len [/ip firewall nat find chain=srcnat action=masquerade out-interface="ether1"]] = 0) do={
    /ip firewall nat add chain=srcnat action=masquerade \
        out-interface=ether1 comment="Optimum-Internet-Sharing"
}
:put "  ✅ NAT configured"


# ── STEP 5B — DNS Resolver ──────────────────────────────────────
:put "Step 5B: Configuring DNS resolver..."
/ip dns set allow-remote-requests=yes servers=8.8.8.8,8.8.4.4
:put "  ✅ DNS resolver enabled"

# ── STEP 6 — Enable API ────────────────────────────────────────
:put "Step 6: Enabling MikroTik API..."
/ip service set api disabled=no port=8728
/ip service set api-ssl disabled=yes
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
:put "  ✅ API enabled on port 8728"

# ── STEP 7 — WiFi SSID ────────────────────────────────────────
:put "Step 7: Configuring WiFi..."
:if ([:len [/interface wireless find]] > 0) do={
    /interface wireless set [find] \
        ssid="KABALAGALA INTERNET" \
        mode=ap-bridge \
        disabled=no
    :if ([:len [/interface bridge port find interface="wlan1" bridge=bridge1]] = 0) do={
        :do { /interface bridge port add interface=wlan1 bridge=bridge1 } on-error={}
    }
    :put "  ✅ WiFi: OPTIMUM HOTSPOT"
} else={
    :put "  ℹ️  No wireless interface — skipping"
}

# ── STEP 8 — Hotspot profile ───────────────────────────────────
:put "Step 8: Configuring hotspot profile..."
:if ([:len [/ip hotspot profile find name="hsprof1"]] = 0) do={
    /ip hotspot profile add \
        name=hsprof1 \
        hotspot-address=$lanIP \
        dns-name=$lanIP \
        login-by=cookie \
        html-directory=hotspot \
        http-cookie-lifetime=1d
} else={
    /ip hotspot profile set [find name="hsprof1"] \
        hotspot-address=$lanIP \
        dns-name=$lanIP \
        login-by=cookie \
        html-directory=hotspot \
        http-cookie-lifetime=1d
}
:put "  ✅ Hotspot profile configured"


# ── STEP 9 — Hotspot ───────────────────────────────────────────
:put "Step 9: Setting up hotspot..."
:if ([:len [/ip hotspot find name="hotspot1"]] = 0) do={
    /ip hotspot add \
        name=hotspot1 \
        interface=bridge1 \
        address-pool=dhcp_pool0 \
        profile=hsprof1 \
        idle-timeout=5m \
        disabled=no
} else={
    /ip hotspot enable [find name="hotspot1"]
}
:put "  ✅ Hotspot running on bridge1"

# ── STEP 10 — Walled garden ─────────────────────────────────────
:put "Step 10: Configuring walled garden..."
/ip hotspot walled-garden remove [find comment="OptimumWiFi"]

/ip hotspot walled-garden add dst-host=$portalDomain \
    action=allow comment="OptimumWiFi"
/ip hotspot walled-garden add dst-host=("*." . $portalDomain) \
    action=allow comment="OptimumWiFi"

:put "  ✅ Walled garden configured"

# ── STEP 11 — Hotspot HTML pages ───────────────────────────────
:put "Step 11: Setting up hotspot pages..."

:local loginContent ("<html><head><meta http-equiv='refresh' content='0;url=https://" . $portalDomain . "/?mac=\$(mac)&ip=\$(ip)&router=\$(identity)'></head><body>Redirecting...</body></html>")

:local redirectContent "<html><head><meta http-equiv='refresh' content='0; url=\$(link-redirect)'></head><body>Redirecting...</body></html>"

:local aloginContent "<html><head><meta http-equiv='refresh' content='0; url=\$(link-redirect)'></head><body>Connecting...</body></html>"

:local errorContent "<html><body><h1>Error</h1><p>\$(error)</p><a href='\$(link-login)'>Try again</a></body></html>"

:local logoutContent "<html><body><h1>Logged Out</h1><a href='\$(link-login)'>Login again</a></body></html>"

:if ([:len [/file find name="hotspot/login.html"]] = 0) do={
    /file add name="hotspot/login.html" contents=$loginContent
} else={
    /file set "hotspot/login.html" contents=$loginContent
}

:if ([:len [/file find name="hotspot/redirect.html"]] = 0) do={
    /file add name="hotspot/redirect.html" contents=$redirectContent
} else={
    /file set "hotspot/redirect.html" contents=$redirectContent
}

:if ([:len [/file find name="hotspot/alogin.html"]] = 0) do={
    /file add name="hotspot/alogin.html" contents=$aloginContent
} else={
    /file set "hotspot/alogin.html" contents=$aloginContent
}

:if ([:len [/file find name="hotspot/error.html"]] = 0) do={
    /file add name="hotspot/error.html" contents=$errorContent
} else={
    /file set "hotspot/error.html" contents=$errorContent
}

:if ([:len [/file find name="hotspot/logout.html"]] = 0) do={
    /file add name="hotspot/logout.html" contents=$logoutContent
} else={
    /file set "hotspot/logout.html" contents=$logoutContent
}

:put "  ✅ All hotspot pages configured"

# ── STEP 12 — Command polling scheduler ────────────────────────
:put "Step 12: Setting up command polling..."
/system scheduler remove [find name="OptimumWiFiPoller"]
/system script remove [find name="OptimumWiFiPoller"]

/system script add name=OptimumWiFiPoller source=(\
    ":local url \"https://" . $portalDomain . "/network/router/" . $routerIdentity . "/commands/\";" .\
    ":do {\r\n" .\
    "/tool fetch url=\$url output=file dst-path=\"wifi-cmds.rsc\"\r\n" .\
    "/import file-name=wifi-cmds.rsc\r\n" .\
    "/file remove wifi-cmds.rsc\r\n" .\
    "} on-error={}")

/system scheduler add \
    name=OptimumWiFiPoller \
    interval=2s \
    on-event=OptimumWiFiPoller \
    comment="Optimum WiFi — polls Django for commands"
:put "  ✅ Command polling every 2 seconds"

# ── STEP 13 — Register with Django ─────────────────────────────
:put "Step 13: Registering with Django portal..."
:local regUrl ("https://" . $portalDomain . "/network/register-router/")
:local body ("{\"identity\":\"" . $routerIdentity . "\",\"location\":\"" . $routerLocation . "\",\"gateway_ip\":\"" . $lanIP . "\",\"api_username\":\"admin\",\"api_password\":\"\",\"api_port\":8728,\"connection_type\":\"direct\"}")

:do {
    /tool fetch \
        url=$regUrl \
        http-method=post \
        http-header-field="Content-Type: application/json" \
        http-data=$body \
        output=none
    :put "  ✅ Registered with Django portal"
} on-error={
    :put "  ⚠️  Could not reach portal — check internet connection"
}

# ── DONE ──────────────────────────────────────────────────────
:put ""
:put "═══════════════════════════════════════════════"
:put "✅ CONFIGURATION COMPLETE — 100% READY"
:put ("   Router  : " . $routerIdentity)
:put ("   Location: " . $routerLocation)
:put "═══════════════════════════════════════════════"
:put ""
:put "ℹ️  Customers connect to WiFi: OPTIMUM HOTSPOT"
:put "ℹ️  ether1 should be connected to internet source"
:put "═══════════════════════════════════════════════"