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
  readonly property string focusControl: {
    if (!panelFocused || !content.Window.window) return ""
    var item = content.Window.window.activeFocusItem
    while (item) {
      if (item.objectName && String(item.objectName).indexOf("vpn") === 0) return String(item.objectName)
      item = item.parent
    }
    return ""
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
  readonly property bool canSwitch: dynamicReady && canDisconnect && targetReady()

  function targetReady() {
    if (!vpn || !dynamicReady || vpn.protocolRefresh || !vpn.selectedCountry
        || !vpn.discovery.items.some(function(item) { return item.code === vpn.selectedCountry })) return false
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

  function open() {
    root.controller.show()
    if (vpn && !vpn.working) vpn.refresh()
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
    while (ancestor && ancestor !== layout) ancestor = ancestor.parent
    if (!ancestor) return
    var y = item.mapToItem(layout, 0, 0).y
    if (y < scroll.contentY) scroll.contentY = y
    else if (y + item.height > scroll.contentY + scroll.height)
      scroll.contentY = y + item.height - scroll.height
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
              Text {
                textFormat: Text.PlainText
                text: "CG"
                font.family: Style.font.family
                font.pixelSize: Style.font.display
                font.bold: true
                color: root.connected ? (root.ink.r + root.ink.g + root.ink.b < 1.5 ? "#866200" : "#ffcf36") : root.ink
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
            text: "Client may disable IPv6. No kill switch."
            font.pixelSize: Style.font.bodySmall
          }
          Action {
            objectName: "vpnConnectAction"
            width: parent.width
            text: root.vpn && root.vpn.busy ? root.vpn.stateText : root.canDisconnect ? "Disconnect VPN"
              : root.dynamicReady ? "Connect selected location" : "Connect VPN"
            enabled: root.vpn && !root.vpn.working && (root.canDisconnect ? true
              : root.vpn.snapshot.can_connect === true && (!root.dynamicReady || root.targetReady()))
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
              options: [{ value: "auto", label: "Automatic" }, { value: "wireguard", label: "WireGuard" }, { value: "openvpn", label: "OpenVPN" }]
              foreground: root.ink
              enabled: root.vpn && !root.vpn.working && !root.vpn.protocolRefresh
              onChanged: function(value) { root.vpn.selectProtocol(value) }
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
            Label { text: "Using existing OpenVPN profile “" + (root.vpn ? root.vpn.profileName : "cyberghost") + "”. Its imported configuration selects the location." }
          }

          Column {
            visible: root.section === "details"
            width: parent.width
            spacing: Style.spacing.controlGap
            Ui.PanelSeparator { foreground: root.ink }
            Ui.PanelSectionHeader { text: "Connection details"; foreground: root.ink }
            Label { text: "Profile   " + (root.vpn ? root.vpn.profileName : "—") }
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
            Label { text: "Optional: contacts api.ipify.org. Connection status does not verify routing, DNS or your location."; font.pixelSize: Style.font.bodySmall }
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
            value: root.vpn ? root.vpn.backendMode : "manual-profile"
            options: root.vpn && root.vpn.hasVendor
              ? [{ value: "manual-profile", label: "Existing OpenVPN" }, { value: "official-cli", label: "Official CLI · experimental" }]
              : [{ value: "manual-profile", label: "Existing OpenVPN" }]
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
            text: root.vpn && root.vpn.working ? "Checking…" : "Refresh diagnostics"
            enabled: root.vpn && !root.vpn.working
            onClicked: root.vpn.refresh()
          }
          Label {
            text: root.vpn && root.vpn.hasVendor ? "Official CLI detected. Arch/Omarchy integration is experimental; connection status does not establish privacy protection."
              : "Official CLI not detected in a trusted system path. Arch/Omarchy is not a vendor-supported platform."
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            text: "No kill switch. DNS and IPv6 leak protection are untested. Automatic connection and reconnection are unavailable."
            font.pixelSize: Style.font.bodySmall
          }
          Label { text: "Protocol and favorites are saved in shell settings. Backend and profile choices last for this session."; font.pixelSize: Style.font.bodySmall }
        }
      }
    }
  }
}
}
