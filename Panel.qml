pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import qs.Commons
import qs.Ui as Ui

Ui.Panel {
  id: root
  moduleName: "petevo.cyberghost"
  manageIpc: false
  property var anchorItem: null
  property var hostWidget: null
  property var vpn: null
  readonly property bool panelFocused: content.Window.window ? content.Window.window.active : false
  readonly property bool reportSelected: reportText.selectedText.length > 0
  readonly property var focusedControlItem: {
    if (!panelFocused || !content.Window.window) return null
    var item = content.Window.window.activeFocusItem
    while (item) {
      if (item.objectName && String(item.objectName).indexOf("vpn") === 0) return item
      item = item.parent
    }
    return null
  }
  readonly property string focusControl: focusedControlItem ? String(focusedControlItem.objectName) : ""
  readonly property var focusRect: {
    if (!focusedControlItem) return null
    var point = focusedControlItem.mapToGlobal(0, 0)
    return { x: point.x, y: point.y, width: focusedControlItem.width, height: focusedControlItem.height }
  }
  readonly property string searchPlaceholder: {
    if (!panelFocused || !content.Window.window) return ""
    var item = content.Window.window.activeFocusItem
    return item && typeof item.placeholderText === "string" ? item.placeholderText : ""
  }
  property string section: "home"
  property string settingsSection: "preferences"
  property bool recoveryHelpExpanded: false
  readonly property color ink: Color.popups.text
  readonly property bool connected: vpn && vpn.snapshot.state === "connected"
  readonly property bool canDisconnect: vpn && vpn.snapshot.can_disconnect === true
  readonly property bool dynamicReady: vpn && vpn.dynamicMode
  readonly property bool canSwitch: dynamicReady && connected && canDisconnect && targetReady()
    && vpn.snapshot.can_switch === true && vpn.selectedProtocol === "wireguard" && !vpn.killSwitch && vpn.snapshot.kill_switch !== true
  onOpenedChanged: if (opened && vpn && !vpn.working) vpn.refresh()

  function targetReady() {
    if (!vpn || !dynamicReady || !vpn.setupReady || vpn.protocolRefresh || !vpn.selectedCountry
        || !vpn.discovery.items.some(function(item) { return item.code === vpn.selectedCountry })) return false
    if (vpn.killSwitch && vpn.selectedProtocol !== "wireguard") return false
    if (vpn.selectedCity && vpn.cities.items.indexOf(vpn.selectedCity) < 0) return false
    return !vpn.selectedServer || vpn.servers.items.some(function(item) { return item.name === vpn.selectedServer })
  }
  function favoriteLabel(item) {
    if (!item || typeof item !== "object") return "Invalid saved location"
    var country = null
    for (var i = 0; i < vpn.discovery.items.length; i++) {
      if (vpn.discovery.items[i].code === item.country) { country = vpn.discovery.items[i]; break }
    }
    return (country ? country.name : item.country) + " · " + (item.city || "Any city") + " · "
      + (item.server || "Automatic server") + " · " + String(item.protocol || "unknown").toUpperCase()
  }
  function favoriteButtonLabel(item) {
    if (!item || typeof item !== "object") return "Invalid saved location"
    return String(item.country || "?") + " · " + (item.city || "Any city") + " · " + String(item.protocol || "auto").toUpperCase()
  }
  function locationSummary() {
    if (vpn && vpn.snapshot.location)
      return (vpn.snapshot.location_source === "requested" ? "Requested location · " : "Reported location · ") + vpn.snapshot.location
    if (dynamicReady && targetReady()) {
      var country = null
      for (var i = 0; i < vpn.discovery.items.length; i++) {
        if (vpn.discovery.items[i].code === vpn.selectedCountry) { country = vpn.discovery.items[i]; break }
      }
      return "Next location · " + (country ? country.name : vpn.selectedCountry) + (vpn.selectedCity ? " · " + vpn.selectedCity : "")
    }
    return "Location · Not reported"
  }
  function selectSection(value) {
    if (section === value) return
    section = value
    Qt.callLater(function() { scroll.contentY = 0 })
  }
  function durationLabel(seconds) {
    if (typeof seconds !== "number" || !isFinite(seconds) || seconds < 0) return ""
    var minutes = Math.floor(seconds / 60)
    var hours = Math.floor(minutes / 60)
    return hours ? hours + "h " + (minutes % 60) + "m" : minutes + "m"
  }
  function byteLabel(value) {
    if (typeof value !== "number" || !isFinite(value) || value < 0 || value > 9007199254740991) return "—"
    const units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    var unit = 0
    while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++ }
    return (unit ? value.toFixed(1) : String(value)) + " " + units[unit]
  }
  function healthLabel() {
    if (!vpn || vpn.statusFailed) return "Connection health unavailable · Refresh status"
    if (vpn.statusStale) return "Status is stale · Refresh before relying on it"
    if (vpn.snapshot.state === "waiting-network") return "Waiting for an upstream network · Connectivity not confirmed"
    if (["blocked", "recovery-required", "unknown"].indexOf(vpn.snapshot.state) >= 0)
      return "Connection needs attention · Check recovery options"
    if (vpn.snapshot.tunnel_detected === true)
      return vpn.snapshot.ipv4_route === true ? "Tunnel detected · IPv4 route present" : "Tunnel detected · IPv4 route missing"
    if (vpn.snapshot.state === "disconnected") return "No active VPN reported"
    if (vpn.snapshot.state === "connected") return (root.dynamicReady ? "Client" : "NetworkManager") + " reports connected · Route not checked"
    return "Connection needs attention · Check recovery options"
  }
  function panelBounds() {
    const point = content.mapToGlobal(-popup.padding - Border.left(popup.borderSpec),
                                     -popup.padding - Border.top(popup.borderSpec))
    return { x: point.x, y: point.y, width: popup.contentWidth, height: popup.contentHeight }
  }
  function revealMessage() {
    Qt.callLater(function() { if (root.opened && errorLabel.visible) root.revealFocus(errorLabel) })
  }
  function revealReport() {
    settingsSection = "support"
    Qt.callLater(function() { if (root.opened && reportScroll.visible) root.revealFocus(reportScroll) })
  }
  function revealUpdates() {
    Qt.callLater(function() { if (root.opened && releaseStatusLabel.visible) root.revealFocus(releaseStatusLabel) })
  }

  function open() {
    root.controller.show()
  }
  function close() {
    countryPicker.close()
    cityPicker.close()
    serverPicker.close()
    quickTargetPicker.close()
    protocolPicker.close()
    backendPicker.close()
    root.controller.hide()
  }

  component Label: Text {
    textFormat: Text.PlainText
    color: root.ink
    font.family: Style.font.family
    font.pixelSize: Style.font.body
    wrapMode: Text.Wrap
    width: parent.width
  }

  component Action: Ui.Button {
    foreground: root.ink
    focusable: true
    opacity: enabled ? 1 : 0.5
    Accessible.role: Accessible.Button
    Accessible.name: text
  }

  function revealFocus(item) {
    var ancestor = item
    while (ancestor && ancestor !== layout) {
      if (ancestor === reportScroll) item = reportScroll
      ancestor = ancestor.parent
    }
    if (!ancestor) return
    var y = item.mapToItem(layout, 0, 0).y
    var targetY = scroll.contentY
    if (y < scroll.contentY) targetY = y
    else if (y + item.height > scroll.contentY + scroll.height)
      targetY = y + item.height - scroll.height
    scroll.contentY = Math.max(0, Math.min(targetY, Math.max(0, scroll.contentHeight - scroll.height)))
  }

  Ui.KeyboardPanel {
    id: popup
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    focusTarget: content
    contentWidth: popup.fittedContentWidth(Style.space(360))
    contentHeight: popup.fittedContentHeight(Math.min(layout.implicitHeight, Style.space(550)))

    // Qt Controls own Tab, arrows and text editing; Escape bubbles to this item.
    Item {
      id: content
      anchors.fill: parent
      focus: true
      Keys.onEscapePressed: root.close()
      Connections {
        target: content.Window.window
        function onActiveFocusItemChanged() {
          if (content.Window.window) root.revealFocus(content.Window.window.activeFocusItem)
        }
      }
      Flickable {
        id: scroll
        anchors.fill: parent
        contentWidth: width
        contentHeight: layout.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Controls.ScrollBar.vertical: Controls.ScrollBar { policy: Controls.ScrollBar.AsNeeded }

        Column {
          id: layout
          width: scroll.width
          spacing: Style.spacing.controlGap

          Ui.PanelHero {
            title: "CyberGhost VPN"
            meta: ""
            foreground: root.ink
            iconComponent: Component {
              GhostIcon {
                implicitWidth: Style.font.display
                implicitHeight: implicitWidth
                color: root.vpn && root.vpn.transitioning ? Color.accent : root.vpn && root.vpn.needsAttention ? Color.urgent
                  : root.connected ? (root.ink.r + root.ink.g + root.ink.b < 1.5 ? "#866200" : "#ffcf36") : root.ink
              }
            }
          }
          Ui.PanelSeparator { foreground: root.ink }
          Ui.ButtonGroup {
            objectName: "vpnSectionTabs"
            width: parent.width
            options: [{ value: "home", label: "Home" }, { value: "locations", label: "Locations" }, { value: "details", label: "Details" }, { value: "settings", label: "Settings" }]
            value: root.section
            foreground: root.ink
            onChanged: function(value) { root.selectSection(value) }
          }
          Action {
            objectName: "vpnSetupShortcut"
            visible: root.vpn && !root.vpn.setupReady
            text: "Complete setup"
            onClicked: { root.settingsSection = "support"; root.selectSection("settings"); Qt.callLater(function() { root.revealFocus(setupHeader) }) }
          }
          Label {
            visible: root.vpn && !root.canDisconnect && root.vpn.setupMessage.length > 0
              && root.vpn.setupMessage !== root.vpn.message
            text: root.vpn ? root.vpn.setupMessage : ""
            Accessible.role: Accessible.AlertMessage
          }
          Action {
            objectName: "vpnCancelQuickConnect"
            visible: root.vpn && root.vpn.quickConnecting
            text: "Cancel Quick Connect"
            onClicked: root.vpn.cancelQuickConnect()
          }
          Action {
            objectName: "vpnConnectAction"
            visible: root.section === "locations"
            width: parent.width
            text: root.vpn && root.vpn.busy ? root.vpn.stateText
              : root.vpn && (root.vpn.snapshot.state === "blocked" || root.vpn.snapshot.state === "recovery-required") ? "Restore normal networking"
              : root.canDisconnect ? "Disconnect VPN"
              : root.dynamicReady ? "Connect selected location" : "Connect VPN"
            enabled: root.vpn && !root.vpn.working && (root.canDisconnect ? true
              : root.vpn.setupReady && root.vpn.snapshot.can_connect === true && (!root.dynamicReady || root.targetReady()))
            bordered: true
            foreground: root.ink
            selected: root.connected
            onClicked: root.vpn.invoke(root.canDisconnect ? "disconnect" : "connect")
          }
          Action {
            visible: root.section === "locations" && root.dynamicReady && root.canDisconnect
            width: parent.width
            objectName: "vpnSwitchAction"
            text: "Switch location"
            enabled: root.canSwitch && !root.vpn.working
            onClicked: root.vpn.invoke("switch")
          }
          Label {
            id: errorLabel
            visible: root.vpn && root.vpn.message.length > 0
            text: root.vpn ? root.vpn.message : ""
            font.bold: true
            Accessible.role: Accessible.AlertMessage
          }
          Action {
            visible: root.vpn && root.vpn.snapshot.state === "unknown"
            text: "Retry status"
            enabled: root.vpn && !root.vpn.working
            onClicked: root.vpn.refresh()
          }

          Column {
            visible: root.section === "home"
            width: parent.width
            spacing: Style.space(16)
            Item { width: 1; height: Style.space(4) }
            Label {
              text: root.vpn ? root.vpn.stateText : "Checking connection…"
              horizontalAlignment: Text.AlignHCenter
              font.pixelSize: Style.font.heading
            }
            Action {
              id: power
              objectName: "vpnPowerAction"
              anchors.horizontalCenter: parent.horizontalCenter
              width: Style.space(116)
              height: width
              radius: width / 2
              bordered: true
              foreground: root.connected ? (root.ink.r + root.ink.g + root.ink.b < 1.5 ? "#866200" : "#ffcf36") : root.ink
              selected: root.connected
              enabled: root.vpn && !root.vpn.working && (root.canDisconnect
                || (root.vpn.setupReady && root.vpn.snapshot.can_connect === true && (!root.dynamicReady || root.targetReady())))
              Accessible.name: root.vpn && ["blocked", "recovery-required"].indexOf(root.vpn.snapshot.state) >= 0 ? "Restore normal networking" : root.canDisconnect ? "Disconnect VPN" : "Connect selected location"
              tooltipText: Accessible.name
              onClicked: root.vpn.invoke(root.canDisconnect ? "disconnect" : "connect")
              Canvas {
                anchors.centerIn: parent
                width: Style.space(40); height: width
                property color ink: power.foreground
                onInkChanged: requestPaint()
                onPaint: {
                  const ctx = getContext("2d")
                  ctx.reset()
                  ctx.strokeStyle = ink
                  ctx.lineWidth = 2.5
                  ctx.lineCap = "round"
                  ctx.beginPath()
                  ctx.arc(width / 2, height / 2 + 2, width * 0.34, -Math.PI * 0.3, Math.PI * 1.3)
                  ctx.stroke()
                  ctx.beginPath()
                  ctx.moveTo(width / 2, 3)
                  ctx.lineTo(width / 2, height * 0.48)
                  ctx.stroke()
                }
              }
            }
            Label {
              text: root.vpn && root.vpn.busy ? root.vpn.stateText
                : root.vpn && ["blocked", "recovery-required"].indexOf(root.vpn.snapshot.state) >= 0 ? "Restore normal networking" : root.canDisconnect ? "Click to disconnect" : "Click to connect"
              horizontalAlignment: Text.AlignHCenter
              font.pixelSize: Style.font.bodySmall
            }
            Action {
              objectName: "vpnLocationShortcut"
              bordered: true
              width: parent.width
              text: root.locationSummary()
              // The accessible full description retains reported/requested provenance.
              Accessible.name: root.locationSummary() + ". Choose a location"
              tooltipText: "Choose a location"
              onClicked: root.selectSection("locations")
            }
            Action {
              objectName: "vpnHomeIpAction"
              width: parent.width
              text: root.vpn && root.vpn.publicIp ? "Last IPv4 · " + root.vpn.publicIp + " · " + root.vpn.ageLabel(root.vpn.publicIpAt)
                : root.vpn && root.vpn.pending === "ip" ? "Checking VPN IPv4…" : "Check VPN IPv4"
              fontSize: Style.font.bodySmall
              enabled: root.connected && root.vpn && !root.vpn.working
              tooltipText: "Explicit lookup through the VPN at api.ipify.org. Click to refresh."
              onClicked: root.vpn.invoke("ip")
            }
            Row {
              width: parent.width
              spacing: Style.space(12)
              Column {
                width: (parent.width - parent.spacing) / 2
                spacing: Style.space(4)
                Label { text: "Downloaded"; font.pixelSize: Style.font.bodySmall; horizontalAlignment: Text.AlignHCenter }
                Label { text: root.connected && root.vpn && !root.vpn.statusStale && !root.vpn.statusFailed ? root.byteLabel(root.vpn.snapshot.download_bytes) : "—"; horizontalAlignment: Text.AlignHCenter }
              }
              Column {
                width: (parent.width - parent.spacing) / 2
                spacing: Style.space(4)
                Label { text: "Uploaded"; font.pixelSize: Style.font.bodySmall; horizontalAlignment: Text.AlignHCenter }
                Label { text: root.connected && root.vpn && !root.vpn.statusStale && !root.vpn.statusFailed ? root.byteLabel(root.vpn.snapshot.upload_bytes) : "—"; horizontalAlignment: Text.AlignHCenter }
              }
            }
            Row {
              width: parent.width
              spacing: Style.space(12)
              Column {
                width: (parent.width - parent.spacing) / 2
                spacing: Style.space(4)
                Label { text: "Protocol"; font.pixelSize: Style.font.bodySmall; horizontalAlignment: Text.AlignHCenter }
                Label { text: root.vpn && root.vpn.snapshot.protocol ? root.vpn.snapshot.protocol : "—"; horizontalAlignment: Text.AlignHCenter }
              }
              Column {
                width: (parent.width - parent.spacing) / 2
                spacing: Style.space(4)
                Label { text: "Duration"; font.pixelSize: Style.font.bodySmall; horizontalAlignment: Text.AlignHCenter }
                Label { text: root.connected && root.vpn && typeof root.vpn.snapshot.duration === "number" ? root.durationLabel(root.vpn.snapshot.duration) : "—"; horizontalAlignment: Text.AlignHCenter }
              }
            }
            Label {
              text: root.vpn && (root.vpn.statusStale || root.vpn.statusFailed || root.vpn.needsAttention)
                ? root.healthLabel() : "Reported connection · Verification in Details"
              horizontalAlignment: Text.AlignHCenter
              font.pixelSize: Style.font.bodySmall
            }
          Action {
            objectName: "vpnQuickConnect"
            visible: root.section === "home" && root.dynamicReady && !root.canDisconnect
            width: parent.width
            text: root.vpn && root.vpn.quickConnecting ? "Checking saved location…" : "Quick Connect"
            enabled: root.vpn && !root.vpn.working && !root.vpn.protocolRefresh && root.vpn.setupReady
              && root.vpn.snapshot.state === "disconnected" && root.vpn.snapshot.can_connect === true && !!root.vpn.quickTarget
            onClicked: root.vpn.quickConnect()
          }
          Label {
            visible: root.section === "home" && root.dynamicReady && !root.canDisconnect
            text: root.vpn && root.vpn.quickTarget ? "Quick Connect · " + root.favoriteLabel(root.vpn.quickTarget)
              : root.vpn && root.vpn.quickTargetKey ? "Quick Connect favorite unavailable. Choose another in Settings."
              : "Connect once or choose a favorite in Settings to enable Quick Connect."
            font.pixelSize: Style.font.bodySmall
          }
          }

          Column {
            visible: root.section === "locations" && root.dynamicReady
            width: parent.width
            spacing: Style.spacing.controlGap
            Ui.PanelSectionHeader { text: "Next connection"; foreground: root.ink }
            Ui.SearchableDropdown {
              id: countryPicker
              objectName: "vpnCountryPicker"
              width: parent.width
              label: "Country"
              placeholderText: "Search countries"
              emptyText: root.vpn && root.vpn.working ? "Loading countries…" : "No countries returned. Refresh to retry."
              value: root.vpn ? root.vpn.selectedCountry : ""
              foreground: root.ink
              enabled: root.vpn && !root.vpn.working && !root.vpn.protocolRefresh && root.vpn.discovery.items.length > 0
              options: root.vpn ? root.vpn.discovery.items.map(function(item) { return { value: item.code, label: item.name } }) : []
              onChanged: function(value) { root.vpn.selectCountry(value) }
            }
            Ui.SearchableDropdown {
              id: cityPicker
              objectName: "vpnCityPicker"
              width: parent.width
              label: "City"
              placeholderText: "Search cities"
              value: root.vpn ? root.vpn.selectedCity : ""
              foreground: root.ink
              enabled: root.vpn && !root.vpn.working && !root.vpn.protocolRefresh && root.vpn.cities.items.length > 0
              options: [{ value: "", label: "Any city" }].concat(root.vpn ? root.vpn.cities.items.map(function(item) { return { value: item, label: item } }) : [])
              onChanged: function(value) { root.vpn.selectCity(value) }
            }
            Ui.Dropdown {
              id: protocolPicker
              objectName: "vpnProtocolPicker"
              width: parent.width
              label: "Protocol"
              value: root.vpn ? root.vpn.selectedProtocol : "auto"
              options: [{ value: "auto", label: "Automatic · experimental" }, { value: "wireguard", label: "WireGuard" }, { value: "openvpn", label: "OpenVPN · experimental" }]
              foreground: root.ink
              enabled: root.vpn && !root.vpn.working && !root.vpn.protocolRefresh
              onChanged: function(value) { root.vpn.selectProtocol(value) }
            }
            Label {
              visible: root.canDisconnect && root.vpn && root.vpn.snapshot.protocol === "WireGuard"
                && root.vpn.selectedProtocol !== "wireguard"
              text: "Next connection · Automatic/OpenVPN does not enable the IPv6 guard. Native IPv6 may bypass the VPN."
              font.pixelSize: Style.font.bodySmall
            }
            Ui.SearchableDropdown {
              id: serverPicker
              objectName: "vpnServerPicker"
              width: parent.width
              label: "Individual server"
              placeholderText: "Search servers"
              emptyText: root.vpn && root.vpn.servers.reason ? root.vpn.servers.reason : "Choose a city to discover individual servers."
              value: root.vpn ? root.vpn.selectedServer : ""
              foreground: root.ink
              enabled: root.vpn && !root.vpn.working && !root.vpn.protocolRefresh && root.vpn.selectedCity.length > 0
              options: [{ value: "", label: "Automatic server" }].concat(root.vpn ? root.vpn.servers.items.map(function(item) {
                return { value: item.name, label: item.name, description: item.load === null || item.load === undefined ? item.city : "Load " + item.load + "%" }
              }) : [])
              onChanged: function(value) { root.vpn.selectServer(value) }
            }
            Label {
              text: root.vpn ? root.vpn.discovery.reason || root.vpn.cities.reason || root.vpn.servers.reason : ""
              visible: text.length > 0
            }
            Repeater {
              model: root.vpn ? root.vpn.favorites : []
              delegate: Row {
                id: favoriteRow
                required property var modelData
                required property int index
                width: parent.width
                spacing: Style.spacing.controlGap
                Action {
                  width: parent.width - removeFavorite.implicitWidth - parent.spacing
                  objectName: "vpnFavorite-" + favoriteRow.index
                  text: root.favoriteButtonLabel(favoriteRow.modelData)
                  leftAlign: true
                  clip: true
                  Accessible.name: root.favoriteLabel(favoriteRow.modelData)
                  tooltipText: root.favoriteLabel(favoriteRow.modelData)
                  enabled: root.vpn && !root.vpn.working && !root.vpn.protocolRefresh
                  onClicked: root.vpn.applyFavorite(favoriteRow.index)
                }
                Action {
                  id: removeFavorite
                  objectName: "vpnRemoveFavorite-" + favoriteRow.index
                  text: "Remove"
                  enabled: root.vpn && !root.vpn.working && !root.vpn.protocolRefresh
                  onClicked: root.vpn.removeFavorite(favoriteRow.index)
                }
              }
            }
            Action {
              width: parent.width
              objectName: "vpnSaveFavorite"
              text: "Save favorite"
              enabled: root.vpn && !root.vpn.working && !root.vpn.protocolRefresh && root.targetReady()
                && !root.vpn.favorites.some(function(item) { return root.vpn.favoriteKey(item) === root.vpn.favoriteKey({
                  country: root.vpn.selectedCountry, city: root.vpn.selectedCity,
                  protocol: root.vpn.selectedProtocol, server: root.vpn.selectedServer
                }) })
              onClicked: root.vpn.saveFavorite()
            }
          }
          Column {
            visible: root.section === "locations" && !root.dynamicReady
            width: parent.width
            spacing: Style.spacing.controlGap
            Label { text: "Uses a saved OpenVPN profile. Choose a valid profile in Settings; its configuration determines the location." }
          }

          Column {
            visible: root.section === "details"
            width: parent.width
            spacing: Style.spacing.controlGap
            Ui.PanelSeparator { foreground: root.ink }
            Ui.PanelSectionHeader { text: "Connection details"; foreground: root.ink }
          Label {
            objectName: "vpnHealthSummary"
            text: root.healthLabel()
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            visible: root.vpn && root.vpn.statusStale && !root.vpn.statusFailed && root.vpn.lastStatusAt > 0
            text: "Last successful status · " + (root.vpn ? root.vpn.ageLabel(root.vpn.lastStatusAt) : "Not checked")
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            visible: root.dynamicReady
            text: root.vpn && root.vpn.snapshot.state === "recovery-required" ? "Protection unconfirmed · Restore or verify in Settings."
              : root.vpn && root.vpn.snapshot.kill_switch === true ? "Kill switch configured · Verify in Settings"
              : root.vpn && root.vpn.snapshot.ipv6_guard === true ? "IPv6 guard configured · No kill switch"
              : root.vpn && (root.vpn.snapshot.protocol === "OpenVPN" || (!root.connected && root.vpn.selectedProtocol !== "wireguard")) ? "Automatic/OpenVPN does not enable the IPv6 guard. Native IPv6 may bypass the VPN. Prefer WireGuard."
              : root.connected ? "Protection is not recorded. Check the client setup."
              : "Protection starts after connection. Check Settings."
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            visible: root.dynamicReady && root.canDisconnect
            text: root.vpn && (root.vpn.snapshot.kill_switch === true || root.vpn.killSwitch)
              ? "Full kill-switch switching is unavailable. The block is retained; disconnect deliberately before starting a new connection."
              : root.vpn && root.vpn.snapshot.can_switch === true && root.vpn.selectedProtocol === "wireguard"
              ? "Switching retains IPv6 guarding. IPv4 and resolver bootstrap DNS can leave during the transition."
              : "Switching needs helper API 5 and an active IPv6-guarded WireGuard session. Disconnect before changing protocols."
            font.pixelSize: Style.font.bodySmall
          }
            Label { text: "Status updated · " + (root.vpn ? root.vpn.ageLabel(root.vpn.lastStatusAt) : "Not checked") }
            Label { text: root.vpn && root.vpn.verificationAt ? "Protection check · " + root.vpn.ageLabel(root.vpn.verificationAt) : "Protection · Not checked for this observed session" }
            Label { text: root.vpn && root.vpn.protectionCheck ? root.vpn.protectionCheck : "A tunnel and route do not establish handshakes, DNS/IPv6 protection or provider identity."; font.pixelSize: Style.font.bodySmall }
            Label { text: "Backend   " + (root.dynamicReady ? "Official CLI" : "NetworkManager") }
            Label { visible: !root.dynamicReady; text: "Profile   " + (root.vpn ? root.vpn.profileName : "—") }
            Label { text: "Protocol  " + (root.vpn && root.vpn.snapshot.protocol ? root.vpn.snapshot.protocol : "Not reported") }
            Label { text: (root.vpn && root.vpn.snapshot.location_source === "requested" ? "Requested location  "
              : root.vpn && root.vpn.snapshot.location ? "Reported location  " : "Location  ")
              + (root.vpn && root.vpn.snapshot.location ? root.vpn.snapshot.location : "Not reported") }
            Label { text: (root.vpn && root.vpn.snapshot.server_source === "requested" ? "Requested server  "
              : root.vpn && root.vpn.snapshot.server_source === "client" ? "Reported server  " : "Server  ")
              + (root.vpn && root.vpn.snapshot.server ? root.vpn.snapshot.server : "Not reported") }
            Label {
              visible: root.connected && root.vpn && typeof root.vpn.snapshot.duration === "number"
              text: "Duration  " + (root.vpn ? root.durationLabel(root.vpn.snapshot.duration) : "")
            }
            Label { visible: !!(root.vpn && root.vpn.snapshot.endpoint); text: "Endpoint  " + (root.vpn ? root.vpn.snapshot.endpoint : "") }
            Label { text: "IPv4      " + (root.vpn && root.vpn.publicIp ? root.vpn.publicIp + " · " + root.vpn.ageLabel(root.vpn.publicIpAt) : "Not checked") }
            Action {
              objectName: "vpnIpAction"
            text: "Check public IPv4"
              enabled: root.connected && root.vpn && !root.vpn.working
              onClicked: root.vpn.invoke("ip")
            }
            Label { text: "Optional: contacts api.ipify.org through the detected VPN interface. Status detects a tunnel and route; it does not continuously check handshakes, DNS or your location."; font.pixelSize: Style.font.bodySmall }
            Label {
              visible: root.connected && root.vpn && root.vpn.snapshot.ipv6_disabled === true
              text: "IPv6 was observed disabled while connected. This does not verify leak protection or whether IPv6 returns after disconnect."
              font.pixelSize: Style.font.bodySmall
            }
          }

          Column {
            visible: root.section === "settings"
            width: parent.width
            spacing: Style.spacing.controlGap
            Ui.PanelSeparator { foreground: root.ink }
            Ui.PanelSectionHeader { text: "Settings & diagnostics"; foreground: root.ink }
          Ui.ButtonGroup {
            objectName: "vpnSettingsTabs"
            width: parent.width
            options: [{ value: "preferences", label: "Preferences" }, { value: "safety", label: "Safety" }, { value: "support", label: "Support" }]
            value: root.settingsSection
            foreground: root.ink
            onChanged: function(value) { root.settingsSection = value; Qt.callLater(function() { scroll.contentY = 0 }) }
          }

          Column {
            width: parent.width
            spacing: Style.spacing.controlGap
            visible: root.settingsSection === "preferences"
          Ui.PanelSectionHeader { text: "Installed versions"; foreground: root.ink }
          Label {
            text: root.vpn && root.vpn.versionReport ? "Plugin · " + root.vpn.versionReport.plugin_version
              + "\nHelper API · " + (root.vpn.versionReport.helper_api || "Unavailable") : "Use Refresh diagnostics to check installed versions."
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            visible: root.vpn && !!root.vpn.versionReport
            text: root.vpn && root.vpn.versionReport ? "Client package · "
              + (root.vpn.versionReport.packages["cyberghostvpn-omarchy"] || root.vpn.versionReport.packages.cyberghostvpn || "Not found") : ""
            font.pixelSize: Style.font.bodySmall
          }
          Action {
            objectName: "vpnCheckUpdates"
            text: root.vpn && root.vpn.pending === "updates" ? "Checking GitHub releases…" : "Check for updates"
            enabled: root.vpn && !root.vpn.working
            onClicked: root.vpn.invoke("updates")
          }
          Label {
            id: releaseStatusLabel
            visible: root.vpn && root.vpn.updatesCheckedAt > 0
            text: root.vpn && root.vpn.releaseInfo ? "Published · " + root.vpn.releaseInfo.tag + (root.vpn.releaseInfo.prerelease ? " · Prerelease" : "")
              + "\nChecked · " + root.vpn.ageLabel(root.vpn.updatesCheckedAt) : "No published release returned."
            font.pixelSize: Style.font.bodySmall
          }
          Action {
            objectName: "vpnReleaseNotes"
            text: "Release notes"
            onClicked: Qt.openUrlExternally(root.vpn && root.vpn.releaseInfo ? root.vpn.releaseInfo.url : "https://github.com/peteVo/cyberghost-omarchy-plugin/releases")
          }
          Ui.TextField {
            objectName: "vpnUpdateCommand"
            width: parent.width
            readOnly: true
            selectByMouse: true
            foreground: root.ink
            text: "omarchy plugin update petevo.cyberghost"
            Accessible.name: "Plugin update command; preserve local edits and run in your local terminal"
          }
          Label {
            text: "Update checks contact GitHub only when requested. Review release notes and preserve local edits before updating. Client-package updates remain a separate reviewed installation."
            font.pixelSize: Style.font.bodySmall
          }
          Ui.Toggle {
            objectName: "vpnNotifications"
            width: parent.width
            label: "Connection notifications"
            checked: root.vpn && root.vpn.notifications
            foreground: root.ink
            onClicked: { root.vpn.notifications = !root.vpn.notifications; root.vpn.persistSettings({ notifications: root.vpn.notifications }) }
          }
          Ui.SearchableDropdown {
            id: quickTargetPicker
            objectName: "vpnQuickTarget"
            visible: root.dynamicReady
            width: parent.width
            label: "Quick Connect location"
            value: root.vpn ? root.vpn.quickTargetKey : ""
            options: [{ value: "", label: "Last successful location" }].concat(root.vpn ? root.vpn.favorites.filter(function(item) { return root.vpn.validTarget(item) }).map(function(item) {
              return { value: root.vpn.favoriteKey(item), label: root.favoriteButtonLabel(item), description: item.server || "Automatic server" }
            }) : [])
            foreground: root.ink
            enabled: root.vpn && !root.vpn.working && !root.vpn.quickConnecting
            onChanged: function(value) { root.vpn.quickTargetKey = value; root.vpn.persistSettings({ quickTargetKey: value }) }
          }
          Label {
            visible: root.dynamicReady && root.vpn && !!root.vpn.quickTarget
            text: "Quick Connect target · " + (root.vpn && root.vpn.quickTarget ? root.favoriteLabel(root.vpn.quickTarget) : "")
            font.pixelSize: Style.font.bodySmall
          }
          Action {
            objectName: "vpnForgetLastLocation"
            visible: root.dynamicReady && root.vpn && root.vpn.validTarget(root.vpn.lastSuccessful)
            text: "Forget last successful location"
            enabled: root.vpn && !root.vpn.working && !root.vpn.quickConnecting
            onClicked: { root.vpn.lastSuccessful = null; root.vpn.persistSettings({ lastSuccessful: null }) }
          }
          Ui.Dropdown {
            id: backendPicker
              objectName: "vpnBackendPicker"
            width: parent.width
            label: "Connection backend"
            value: root.vpn ? root.vpn.backendMode : "official-cli"
            options: [{ value: "manual-profile", label: "Existing OpenVPN" }, { value: "official-cli", label: "Official CLI · experimental" }]
            foreground: root.ink
            enabled: root.vpn && !root.vpn.working && (root.vpn.snapshot.state === "disconnected" || root.vpn.snapshot.state === "unknown")
            onChanged: function(value) { root.vpn.selectBackend(value) }
          }
          Ui.TextField {
            id: profileField
              objectName: "vpnProfileField"
            visible: !root.dynamicReady
            width: parent.width
            text: root.vpn ? root.vpn.profileName : "cyberghost"
            maximumLength: 128
            placeholderText: "Existing OpenVPN profile name"
            Accessible.name: "Existing OpenVPN profile name"
            foreground: root.ink
            enabled: root.vpn && !root.vpn.working && !root.canDisconnect
            onAccepted: root.vpn.selectProfile(text)
          }
          Action {
            visible: !root.dynamicReady
            text: "Use profile"
            enabled: root.vpn && !root.vpn.working && !root.canDisconnect && profileField.text.length > 0
            onClicked: root.vpn.selectProfile(profileField.text)
          }

          }

          Column {
            width: parent.width
            spacing: Style.spacing.controlGap
            visible: root.settingsSection === "safety"
          Ui.PanelSectionHeader { text: "Recovery"; foreground: root.ink }
          Ui.Toggle {
            objectName: "vpnRecoveryToggle"
            visible: root.dynamicReady
            width: parent.width
            label: "Recovery for this shell session"
            checked: root.vpn && root.vpn.recoveryEnabled
            enabled: root.vpn && !root.vpn.working
            foreground: root.ink
            onClicked: root.vpn.setRecovery(!root.vpn.recoveryEnabled)
          }
          Label {
            visible: root.dynamicReady
            text: root.vpn ? root.vpn.recoveryMessage : "Off"
            font.pixelSize: Style.font.bodySmall
          }
          Action {
            objectName: "vpnRecoveryHelp"
            visible: root.dynamicReady
            text: root.recoveryHelpExpanded ? "Hide recovery details" : "How recovery works"
            onClicked: root.recoveryHelpExpanded = !root.recoveryHelpExpanded
          }
          Label {
            visible: root.dynamicReady && root.recoveryHelpExpanded
            text: "Enable before connecting. Keeps an existing tunnel while waiting for Wi-Fi, then allows up to two reconnect attempts only after fresh safe status. Authorization may be required. Disconnects and selection changes cancel recovery. Guarded retries require helper API 6 and the same confirmed target; a full traffic block needs manual recovery. Disable before managing the VPN elsewhere."
            font.pixelSize: Style.font.bodySmall
          }
          Ui.Toggle {
            objectName: "vpnKillSwitchToggle"
            visible: root.dynamicReady
            width: parent.width
            label: "Kill switch · WireGuard"
            checked: root.vpn && (root.canDisconnect ? root.vpn.snapshot.kill_switch === true : root.vpn.killSwitch)
            enabled: root.vpn && !root.vpn.working && !root.canDisconnect
              && (root.vpn.selectedProtocol === "wireguard" || checked)
            opacity: enabled ? 1 : 0.5
            foreground: root.ink
            Accessible.role: Accessible.CheckBox
            Accessible.name: label
            Accessible.checkable: true
            Accessible.checked: checked
            onClicked: root.vpn.setKillSwitch(!checked)
          }
          Label {
            visible: root.dynamicReady
            text: "Starts after connection. Unexpected tunnel loss retains the block. Disconnect releases it; full kill-switch location switches are refused."
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            visible: root.dynamicReady && root.vpn && root.vpn.killSwitch && root.vpn.selectedProtocol !== "wireguard"
            text: "Choose WireGuard or turn off the kill switch before connecting."
            font.pixelSize: Style.font.bodySmall
          }
          Action {
            objectName: "vpnVerifyProtection"
            visible: root.vpn && root.vpn.snapshot.can_release_protection === true
            text: "Verify traffic protection"
            enabled: root.vpn && !root.vpn.working
            onClicked: root.vpn.invoke("verify-protection")
          }
          Label {
            visible: root.vpn && root.vpn.protectionCheck.length > 0
            text: root.vpn ? root.vpn.protectionCheck : ""
            font.pixelSize: Style.font.bodySmall
          }
          Action {
            objectName: "vpnReleaseProtection"
            visible: root.vpn && root.vpn.snapshot.can_release_protection === true
              && root.vpn.snapshot.state !== "connected" && root.vpn.snapshot.state !== "waiting-network"
            text: "Release CyberGhost traffic block"
            enabled: root.vpn && !root.vpn.working
            onClicked: root.vpn.invoke("release-protection")
          }
          Label {
            visible: root.vpn && root.vpn.snapshot.can_release_protection === true
            text: "Releasing the block allows normal networking without disconnecting other VPNs."
            font.pixelSize: Style.font.bodySmall
          }
          Label { text: "Recovery is session-only, never enabled at login. Preferences and favorites are saved locally."; font.pixelSize: Style.font.bodySmall }
          }

          Column {
            width: parent.width
            spacing: Style.spacing.controlGap
            visible: root.settingsSection === "support"
          Action {
            objectName: "vpnRefreshDiagnostics"
            text: root.vpn && root.vpn.working ? "Checking…" : "Refresh diagnostics"
            enabled: root.vpn && !root.vpn.working
            onClicked: root.vpn.refresh()
          }
          Ui.PanelSectionHeader { id: setupHeader; text: "Setup checklist"; foreground: root.ink }
          Label {
            text: !root.vpn || !root.vpn.setupChecks.length ? "Checking local prerequisites…"
              : root.vpn.setupReady ? (root.dynamicReady ? "System checks passed. Complete local authentication, then connect."
                : "System checks passed. Use an existing OpenVPN profile with valid provider credentials.")
              : "Resolve the items marked Needs attention, then refresh diagnostics."
            font.pixelSize: Style.font.bodySmall
          }
          Repeater {
            model: root.vpn ? root.vpn.setupChecks : []
            delegate: Label {
              required property var modelData
              text: (modelData.ready === true ? "Ready · " : "Needs attention · ") + modelData.label
                + (modelData.ready === true ? "" : "\n" + modelData.message)
              font.pixelSize: Style.font.bodySmall
            }
          }
          Label {
            visible: root.dynamicReady && root.vpn && root.vpn.setupReady
            text: "Account setup · Not inspected. Authentication is checked only when connecting."
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            visible: root.dynamicReady
            text: root.vpn && root.vpn.hasVendor ? "Official CLI detected. Arch/Omarchy integration is experimental; connection status does not establish privacy protection."
              : "Official CLI not detected in a trusted system path. Arch/Omarchy is not a vendor-supported platform."
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            visible: root.dynamicReady
            text: "Install → review system checks → authenticate locally → connect. The panel never installs packages or handles credentials."
            font.pixelSize: Style.font.bodySmall
          }
          Ui.TextField {
            objectName: "vpnSetupCommand"
            visible: root.dynamicReady
            width: parent.width
            text: "sudo cyberghostvpn --setup"
            readOnly: true
            selectByMouse: true
            foreground: root.ink
            Accessible.name: "Official client account setup command; copy to your local terminal"
          }
          Action {
            objectName: "vpnInstallGuide"
            text: "Installation and recovery guide"
            onClicked: Qt.openUrlExternally("https://github.com/peteVo/cyberghost-omarchy-plugin#installation")
          }
          Action {
            objectName: "vpnSupportReport"
            text: root.vpn && root.vpn.pending === "diagnostics" ? "Generating report…" : "Generate shareable diagnostic report"
            enabled: root.vpn && !root.vpn.working
            onClicked: root.vpn.invoke("diagnostics")
          }
          Label {
            visible: root.vpn && root.vpn.diagnosticReport.length > 0
            text: "Report contains versions and setup checks only. Select the text below and copy it into a bug report. No connection or leak test is performed."
            font.pixelSize: Style.font.bodySmall
          }
          Controls.ScrollView {
            id: reportScroll
            visible: root.vpn && root.vpn.diagnosticReport.length > 0
            width: parent.width
            height: Style.space(160)
            contentWidth: availableWidth
            clip: true
            Controls.TextArea {
              id: reportText
              objectName: "vpnReportText"
              width: reportScroll.availableWidth
              text: root.vpn ? root.vpn.diagnosticReport : ""
              textFormat: TextEdit.PlainText
              readOnly: true
              selectByMouse: true
              wrapMode: TextEdit.Wrap
              color: root.ink
              selectionColor: Style.selectionFillFor(root.ink, Color.accent)
              selectedTextColor: root.ink
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              background: null
              Accessible.name: "Shareable diagnostic report"
            }
          }

          }

        }
      }
    }
  }
}
}
