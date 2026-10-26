import QtQuick
import QtQuick.Controls as Controls
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "petevo.cyberghost"
  manageIpc: false
  property var anchorItem: null
  property var hostWidget: null
  property var vpn: null
  readonly property color ink: root.bar ? root.bar.barForeground : Color.foreground
  readonly property color muted: Qt.rgba(ink.r, ink.g, ink.b, 0.72)
  readonly property color gold: "#ffcf36"
  readonly property bool connected: vpn && vpn.snapshot.state === "connected"
  readonly property bool dynamicReady: vpn && vpn.dynamicMode
  onDynamicReadyChanged: if (dynamicReady && root.opened) vpn.invoke("countries")

  function open() {
    root.controller.show()
    if (vpn && vpn.dynamicMode) vpn.invoke("countries")
  }
  function close() { root.controller.hide() }
  function switchPanel(direction) {
    return root.bar && typeof root.bar.switchPanelFrom === "function"
      ? root.bar.switchPanelFrom(root.hostWidget || root, direction) : false
  }

  KeyboardPanel {
    id: popup
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    focusTarget: catcher
    contentWidth: popup.fittedContentWidth(Style.space(360))
    contentHeight: popup.fittedContentHeight(Math.min(layout.implicitHeight, Style.space(560)))

    PanelKeyCatcher {
      id: catcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Flickable {
        anchors.fill: parent
        contentWidth: width
        contentHeight: layout.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Controls.ScrollBar.vertical: Controls.ScrollBar { policy: Controls.ScrollBar.AsNeeded }

        Column {
          id: layout
          width: parent.width
          spacing: Style.space(10)
          Row {
            spacing: Style.space(9)
            Rectangle {
              width: 38
              height: 38
              radius: 12
              color: root.gold
              Text {
                anchors.centerIn: parent
                text: "CG"
                font.bold: true
                font.pixelSize: 15
                color: "#171818"
              }
            }
            Column {
              spacing: 3
              Text {
                text: "CyberGhost VPN"
                font.bold: true
                font.pixelSize: 18
                color: root.ink
              }
              Text {
                text: root.vpn ? root.vpn.snapshot.state.toUpperCase() + " · " +
                  (root.dynamicReady ? "Official CLI" : "Manual profile") : "Loading"
                font.pixelSize: 11
                color: root.muted
              }
            }
          }

          Rectangle {
            width: parent.width
            height: 1
            color: Qt.rgba(root.ink.r, root.ink.g, root.ink.b, 0.13)
          }
          Text {
            width: parent.width
            text: root.dynamicReady
              ? "Countries and cities use CyberGhost's official CLI. Tunnel and leak protection still require independent verification."
              : "Dynamic locations unavailable: CyberGhost does not support its official Linux CLI on Arch. Your imported NetworkManager VPN remains usable below."
            color: root.muted
            font.pixelSize: 12
            wrapMode: Text.Wrap
          }

          Controls.Button {
            width: parent.width
            height: 42
            enabled: root.vpn && !root.vpn.busy && root.vpn.snapshot.backend !== "checking"
            text: !root.vpn ? "Loading…" : root.vpn.busy ? "Working…"
                : root.connected ? "Disconnect VPN" : "Connect VPN"
            font.bold: true
            onClicked: root.vpn.invoke(root.connected ? "disconnect" : "connect")
            background: Rectangle {
              radius: 10
              color: parent.enabled ? root.gold : Qt.rgba(root.ink.r, root.ink.g, root.ink.b, 0.13)
            }
            contentItem: Text {
              text: parent.text
              color: "#161819"
              font: parent.font
              horizontalAlignment: Text.AlignHCenter
              verticalAlignment: Text.AlignVCenter
            }
          }

          Column {
            width: parent.width
            spacing: Style.space(5)
            visible: root.dynamicReady
            Text { text: "LOCATION"; color: root.muted; font.pixelSize: 11; font.bold: true }
            Controls.TextField {
              id: searchField
              width: parent.width
              placeholderText: "Search countries"
              Accessible.name: "Search countries"
            }
            Column {
              width: parent.width
              spacing: 2
              Repeater {
                model: root.vpn && root.vpn.discovery.items
                  ? root.vpn.discovery.items.filter(function(item) {
                      return (item.name + " " + item.code).toLowerCase().indexOf(
                        searchField.text.toLowerCase()) >= 0
                    }).slice(0, 15) : []
                delegate: Controls.Button {
                  required property var modelData
                  width: layout.width
                  height: 30
                  text: modelData.name + "  ·  " + modelData.code
                  font.pixelSize: 12
                  onClicked: {
                    root.vpn.selectedCountry = modelData.code
                    root.vpn.selectedCity = ""
                    root.vpn.invoke("cities")
                  }
                  background: Rectangle {
                    radius: 7
                    color: root.vpn.selectedCountry === parent.modelData.code
                      ? Qt.rgba(root.gold.r, root.gold.g, root.gold.b, 0.18)
                      : "transparent"
                  }
                  contentItem: Text {
                    text: parent.text
                    color: root.ink
                    font: parent.font
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 8
                  }
                }
              }
            }
            Text {
              width: parent.width
              visible: root.vpn && root.vpn.discovery.reason !== ""
              text: root.vpn ? root.vpn.discovery.reason : ""
              color: root.muted
              font.pixelSize: 11
              wrapMode: Text.Wrap
            }
            Text {
              text: "SELECTED  ·  " + (root.vpn ? root.vpn.selectedCountry : "")
              color: root.ink
              font.pixelSize: 12
              font.bold: true
            }
            Controls.TextField {
              id: cityField
              width: parent.width
              placeholderText: "City (optional · auto select if empty)"
              text: root.vpn ? root.vpn.selectedCity : ""
              onTextEdited: root.vpn.selectedCity = text
              Accessible.name: "City"
            }
            Connections {
              target: root.vpn
              function onSelectedCityChanged() {
                if (root.vpn && cityField.text !== root.vpn.selectedCity)
                  cityField.text = root.vpn.selectedCity
              }
            }
            Row {
              width: parent.width
              spacing: Style.space(5)
              Repeater {
                model: root.vpn && root.vpn.cities.items ? root.vpn.cities.items.slice(0, 5) : []
                delegate: Controls.Button {
                  required property var modelData
                  text: modelData
                  font.pixelSize: 11
                  onClicked: root.vpn.selectedCity = modelData
                }
              }
            }
            Text {
              width: parent.width
              text: root.vpn ? root.vpn.cities.reason : ""
              visible: text.length > 0
              wrapMode: Text.Wrap
              color: root.muted
              font.pixelSize: 11
            }
            Text {
              width: parent.width
              text: "Specific servers: unavailable via the documented CLI interface."
              color: root.muted
              font.pixelSize: 11
              wrapMode: Text.Wrap
            }
          }

          Column {
            visible: root.vpn && !root.vpn.dynamicMode
            width: parent.width
            spacing: Style.space(5)
            Text {
              text: "NETWORKMANAGER PROFILE"
              color: root.muted
              font.pixelSize: 11
              font.bold: true
            }
            Controls.TextField {
              width: parent.width
              text: root.vpn ? root.vpn.profileName : "openvpn"
              onTextEdited: root.vpn.profileName = text
              Accessible.name: "NetworkManager profile name"
            }
            Text {
              width: parent.width
              text: "Existing profile only. New locations require another authorized configuration."
              color: root.muted
              font.pixelSize: 11
              wrapMode: Text.Wrap
            }
          }

          Rectangle {
            width: parent.width
            height: 1
            color: Qt.rgba(root.ink.r, root.ink.g, root.ink.b, 0.13)
          }
          Row {
            spacing: Style.space(8)
            Controls.Button { text: "Refresh"; enabled: root.vpn && !root.vpn.busy; onClicked: root.vpn.invoke("status") }
            Controls.Button {
              text: "Check public IP"
              enabled: root.connected && !root.vpn.busy
              onClicked: root.vpn.invoke("ip")
            }
          }
          Text {
            text: root.vpn && root.vpn.publicIp ? "Public IPv4: " + root.vpn.publicIp : "Public IP: not checked"
            color: root.ink
            font.pixelSize: 12
          }
          Text {
            width: parent.width
            visible: root.vpn && root.vpn.message.length > 0
            text: root.vpn ? root.vpn.message : ""
            color: "#dca06c"
            wrapMode: Text.Wrap
            font.pixelSize: 12
          }
          Text {
            width: parent.width
            text: "No kill switch · no DNS/IPv6 leak guarantees · a connected indicator alone does not establish privacy."
            color: root.muted
            wrapMode: Text.Wrap
            font.pixelSize: 10
          }
        }
      }
    }
  }
}
