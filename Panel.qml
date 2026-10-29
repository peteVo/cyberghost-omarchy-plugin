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
  property string section: "locations"
  readonly property color ink: Color.popups.text
  readonly property bool connected: vpn && vpn.snapshot.state === "connected"
  readonly property bool canDisconnect: vpn && vpn.snapshot.can_disconnect === true
  readonly property bool dynamicReady: vpn && vpn.dynamicMode
  readonly property bool canSwitch: dynamicReady && connected && canDisconnect && targetReady()
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
  function panelBounds() {
    const point = content.mapToGlobal(-popup.padding - Border.left(popup.borderSpec),
                                     -popup.padding - Border.top(popup.borderSpec))
    return { x: point.x, y: point.y, width: popup.contentWidth, height: popup.contentHeight }
  }
  function revealMessage() {
    Qt.callLater(function() { if (root.opened && errorLabel.visible) root.revealFocus(errorLabel) })
  }
  function revealReport() {
    Qt.callLater(function() { if (root.opened && reportScroll.visible) root.revealFocus(reportScroll) })
  }

  function open() {
    root.controller.show()
  }
  function close() {
    countryPicker.close()
    cityPicker.close()
    serverPicker.close()
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
            meta: root.vpn ? root.vpn.stateText : "Checking connection…"
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
            options: [{ value: "locations", label: "Locations" }, { value: "details", label: "Details" }, { value: "settings", label: "Settings" }]
            value: root.section
            foreground: root.ink
            onChanged: function(value) { root.selectSection(value) }
          }
          Label {
            text: root.locationSummary()
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            text: (root.vpn && root.vpn.snapshot.protocol ? "Reported protocol · " : "Protocol · ")
              + (root.vpn && root.vpn.snapshot.protocol ? root.vpn.snapshot.protocol : "Not reported")
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            text: (root.vpn && root.vpn.snapshot.server_source === "requested" ? "Requested server · "
              : root.vpn && root.vpn.snapshot.server_source === "client" ? "Reported server · " : "Server · ")
              + (root.vpn && root.vpn.snapshot.server ? root.vpn.snapshot.server : "Not reported")
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            visible: root.vpn && root.vpn.publicIp.length > 0
            text: "Public IPv4 · " + (root.vpn ? root.vpn.publicIp + " (last lookup)" : "")
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
            visible: root.vpn && root.vpn.pending === "switch" && root.vpn.snapshot.kill_switch === true
            text: "Switching temporarily releases the traffic block."
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            visible: root.vpn && !root.canDisconnect && root.vpn.setupMessage.length > 0
              && root.vpn.setupMessage !== root.vpn.message
            text: root.vpn ? root.vpn.setupMessage : ""
            Accessible.role: Accessible.AlertMessage
          }
          Action {
            objectName: "vpnConnectAction"
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
            visible: root.dynamicReady && root.canDisconnect
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
              onChanged: function(value) { root.vpn.selectedServer = value }
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
            Label { text: "IPv4      " + (root.vpn && root.vpn.publicIp ? root.vpn.publicIp + " (last lookup)" : "Not checked") }
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
          Action {
            objectName: "vpnRefreshDiagnostics"
            text: root.vpn && root.vpn.working ? "Checking…" : "Refresh diagnostics"
            enabled: root.vpn && !root.vpn.working
            onClicked: root.vpn.refresh()
          }
          Repeater {
            model: root.vpn ? root.vpn.setupChecks.filter(function(item) { return item.ready !== true }) : []
            delegate: Label {
              required property var modelData
              text: (modelData.ready === true ? "Ready · " : "Needs attention · ") + modelData.label
                + (modelData.ready === true ? "" : "\n" + modelData.message)
              font.pixelSize: Style.font.bodySmall
            }
          }
          Label {
            visible: root.vpn && root.vpn.setupReady
            text: "Local setup is ready. Account authentication is checked when connecting."
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            text: root.vpn && root.vpn.hasVendor ? "Official CLI detected. Arch/Omarchy integration is experimental; connection status does not establish privacy protection."
              : "Official CLI not detected in a trusted system path. Arch/Omarchy is not a vendor-supported platform."
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            visible: root.dynamicReady
            text: "First use: install the reviewed client package, then run account setup in your own terminal. Enter credentials only in the official client."
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
            text: "Starts after connection. Unexpected tunnel loss retains the block. Disconnects and location switches release it."
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
          Label { text: "Automatic server reconnection is unavailable. Preferences and favorites are saved locally."; font.pixelSize: Style.font.bodySmall }
        }
      }
    }
  }
}
}
