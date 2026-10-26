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
  readonly property color ink: Color.popups.text
  readonly property bool connected: vpn && vpn.snapshot.state === "connected"
  readonly property bool canDisconnect: vpn && vpn.snapshot.can_disconnect === true
  readonly property bool dynamicReady: vpn && vpn.dynamicMode

  function open() {
    root.controller.show()
    if (vpn && !vpn.working) vpn.refresh()
  }
  function close() {
    countryPicker.close()
    cityPicker.close()
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
                color: root.connected ? "#ffcf36" : root.ink
              }
            }
          }
          Ui.PanelSeparator { foreground: root.ink }
          Action {
            width: parent.width
            text: root.vpn && root.vpn.busy ? root.vpn.stateText : root.canDisconnect ? "Disconnect VPN" : "Connect VPN"
            enabled: root.vpn && !root.vpn.working && (root.canDisconnect ? true
              : root.vpn.snapshot.can_connect === true && (!root.dynamicReady || root.vpn.selectedCountry.length > 0))
            bordered: true
            foreground: root.ink
            selected: root.connected
            onClicked: root.vpn.invoke(root.canDisconnect ? "disconnect" : "connect")
          }
          Label {
            text: root.dynamicReady ? "Experimental CLI mode. Location switching has not been verified on this machine."
              : "Existing OpenVPN profile. Its imported configuration determines the location."
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
            visible: root.dynamicReady
            width: parent.width
            spacing: Style.spacing.controlGap
            Ui.PanelSectionHeader { text: "Next connection"; foreground: root.ink }
            Ui.SearchableDropdown {
              id: countryPicker
              width: parent.width
              label: "Country"
              placeholderText: "Search countries"
              emptyText: root.vpn && root.vpn.working ? "Loading countries…" : "No countries returned. Refresh to retry."
              value: root.vpn ? root.vpn.selectedCountry : ""
              foreground: root.ink
              enabled: root.vpn && !root.vpn.working
              options: root.vpn ? root.vpn.discovery.items.map(function(item) { return { value: item.code, label: item.name } }) : []
              onChanged: function(value) {
                root.vpn.selectedCountry = value
                root.vpn.selectedCity = ""
                root.vpn.invoke("cities")
              }
            }
            Ui.SearchableDropdown {
              id: cityPicker
              width: parent.width
              label: "City"
              placeholderText: "Search cities"
              value: root.vpn ? root.vpn.selectedCity : ""
              foreground: root.ink
              enabled: root.vpn && !root.vpn.working && root.vpn.selectedCountry.length > 0
              options: [{ value: "", label: "Automatic server" }].concat(root.vpn ? root.vpn.cities.items.map(function(item) { return { value: item, label: item } }) : [])
              onChanged: function(value) { root.vpn.selectedCity = value }
            }
            Label {
              text: root.vpn ? root.vpn.discovery.reason || root.vpn.cities.reason : ""
              visible: text.length > 0
            }
            Label { text: "Disconnect before connecting to another location. Individual-server controls await live verification." }
          }

          Ui.PanelSeparator { foreground: root.ink }
          Ui.PanelSectionHeader { text: "Connection details"; foreground: root.ink }
          Label { text: "Profile   " + (root.vpn ? root.vpn.profileName : "—") }
          Label { text: "Protocol  " + (root.vpn && root.vpn.snapshot.protocol ? root.vpn.snapshot.protocol : "Not reported") }
          Label { text: "Location  " + (root.vpn && root.vpn.snapshot.location ? root.vpn.snapshot.location : "Not reported") }
          Label { text: "Server    " + (root.vpn && root.vpn.snapshot.server ? root.vpn.snapshot.server : "Not reported") }
          Label { text: "IPv4      " + (root.vpn && root.vpn.publicIp ? root.vpn.publicIp + " (last lookup)" : "Not checked") }
          Action {
            text: "Check public IPv4"
            enabled: root.connected && root.vpn && !root.vpn.working
            onClicked: root.vpn.invoke("ip")
          }
          Label { text: "Optional: contacts api.ipify.org. Connection status does not verify routing, DNS or your location."; font.pixelSize: Style.font.bodySmall }

          Ui.PanelSeparator { foreground: root.ink }
          Ui.PanelSectionHeader { text: "Settings & diagnostics"; foreground: root.ink }
          Ui.Dropdown {
            id: backendPicker
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
            text: root.vpn && root.vpn.hasVendor ? "System CLI detected; its live operation remains unverified."
              : "Official CLI not detected in a trusted system path. Arch/Omarchy is not a vendor-supported platform."
            font.pixelSize: Style.font.bodySmall
          }
          Label {
            text: "No kill switch. DNS and IPv6 leak protection are untested. Automatic connection and reconnection are unavailable."
            font.pixelSize: Style.font.bodySmall
          }
          Label { text: "Settings apply to this shell session."; font.pixelSize: Style.font.bodySmall }
        }
      }
    }
  }
}
