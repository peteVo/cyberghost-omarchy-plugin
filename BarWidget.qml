import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui as Ui

Ui.BarWidget {
  id: root
  moduleName: "petevo.cyberghost"
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  property var snapshot: ({ backend: "checking", state: "unknown" })
  property var discovery: ({ items: [], reason: "" })
  property var cities: ({ items: [], reason: "" })
  property string selectedCountry: "DE"
  property string selectedCity: ""
  property string profileName: "openvpn"
  property string publicIp: ""
  property string message: ""
  property bool busy: false
  property string pending: ""
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false
  readonly property string runner: String(Qt.resolvedUrl("cg_bridge.py")).replace(/^file:\/\//, "")
  readonly property bool dynamicMode: snapshot.backend === "official-cli"

  function open() { if (panelLoader.item) panelLoader.item.open() }
  function close() { if (panelLoader.item) panelLoader.item.close() }
  function toggle() { if (panelLoader.item) panelLoader.item.toggle() }
  function closeForPopoutSwitch() { if (panelLoader.item) panelLoader.item.closeForPopoutSwitch() }
  function injectPanel() {
    if (!panelLoader.item) return
    panelLoader.item.bar = root.bar
    panelLoader.item.anchorItem = button
    panelLoader.item.hostWidget = root
    panelLoader.item.vpn = root
  }
  onBarChanged: injectPanel()

  function invoke(task) {
    if (process.running) {
      if (task === "status") return
      message = "An operation is in progress."
      return
    }
    var args = ["/usr/bin/python3", runner, task, "--profile", profileName]
    if (task === "connect" || task === "cities") {
      args.push("--country", selectedCountry)
      if (task === "connect" && selectedCity.length)
        args.push("--city", selectedCity)
    }
    message = ""
    pending = task
    if (task === "connect" || task === "disconnect") publicIp = ""
    busy = task === "connect" || task === "disconnect"
    process.command = args
    process.running = true
  }

  function receive(raw) {
    var data
    try { data = JSON.parse(raw) } catch (e) {
      message = "Cannot read the VPN helper response. Check your Python installation."
      busy = false
      return
    }
    if (!data.ok) {
      message = data.error || "VPN operation failed."
      busy = false
      if (pending === "connect" || pending === "disconnect")
        snapshot = ({ backend: snapshot.backend, state: "unknown" })
      return
    }
    if (pending === "countries") discovery = data
    else if (pending === "cities") cities = data
    else if (pending === "ip") publicIp = data.ip || ""
    else if (pending === "check")
      snapshot = ({ backend: data.backend, state: "unknown" })
    else if (data.state !== undefined) snapshot = data
    busy = false
  }

  Process {
    id: process
    stdout: StdioCollector { onStreamFinished: root.receive(text) }
    stderr: StdioCollector {}
    onExited: function (exitCode) {
      if (exitCode !== 0 && !root.message)
        root.message = "The VPN helper exited unsuccessfully."
      root.busy = false
      if (root.pending === "check")
        Qt.callLater(function () { root.invoke("status") })
    }
  }

  Timer {
    interval: 15000
    repeat: true
    running: true
    onTriggered: if (!process.running) root.invoke("status")
  }
  Component.onCompleted: invoke("check")

  Loader {
    id: panelLoader
    active: true
    visible: false
    source: Qt.resolvedUrl("Panel.qml")
    onLoaded: { root.injectPanel(); Qt.callLater(root.injectPanel) }
  }
  Ui.BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    active: root.opened
    tooltipText: "CyberGhost VPN: " + root.snapshot.state
    Accessible.name: tooltipText
    iconComponent: Component {
      Item {
        anchors.fill: parent
        Text {
          anchors.centerIn: parent
          text: "CG"
          font.bold: true
          font.pixelSize: 11
          font.family: root.bar ? root.bar.fontFamily : "sans-serif"
          color: root.snapshot.state === "connected"
            ? "#ffcf36" : (root.bar ? root.bar.barForeground : "white")
        }
      }
    }
    onPressed: function(code) { if (code === Qt.LeftButton) root.toggle() }
  }
  Rectangle {
    width: 5
    height: 5
    radius: 3
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    color: root.busy ? "#ffcf36"
      : root.snapshot.state === "connected" ? "#3cc795"
      : root.snapshot.state === "unknown" ? "#e99e62" : "transparent"
  }
}
