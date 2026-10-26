pragma ComponentBehavior: Bound
import QtQuick
import Quickshell.Io
import qs.Commons
import qs.Ui as Ui

Ui.BarWidget {
  id: root
  moduleName: "petevo.cyberghost"
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  property var snapshot: ({ backend: "manual-profile", state: "unknown", can_connect: false, can_disconnect: false })
  property var discovery: ({ items: [], reason: "" })
  property var cities: ({ items: [], reason: "" })
  property string backendMode: String(setting("backend", "manual-profile"))
  property string profileName: String(setting("profile", "cyberghost"))
  property string selectedCountry: ""
  property string selectedCity: ""
  property string publicIp: ""
  property string message: ""
  property string pending: ""
  property bool awaiting: false
  property int helperExit: -1
  property bool hasVendor: false
  readonly property bool busy: awaiting && (pending === "connect" || pending === "disconnect")
  readonly property bool working: awaiting
  readonly property bool dynamicMode: backendMode === "official-cli"
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false
  readonly property string runner: decodeURIComponent(String(Qt.resolvedUrl("cg_bridge.py")).replace(/^file:\/\//, ""))
  readonly property string stateText: busy ? (pending === "connect" ? "Connecting…" : "Disconnecting…")
    : snapshot.state === "connected" ? "Connected"
    : snapshot.state === "disconnected" ? "Disconnected"
    : snapshot.state === "connecting" ? "Connecting…"
    : snapshot.state === "disconnecting" ? "Disconnecting…"
    : message ? "Status unavailable" : "Checking connection…"

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

  function refresh() {
    if (!working) invoke("check")
  }
  function selectBackend(value) {
    if (working || value === backendMode) return
    backendMode = value
    selectedCountry = ""
    selectedCity = ""
    discovery = ({ items: [], reason: "" })
    cities = ({ items: [], reason: "" })
    publicIp = ""
    snapshot = ({ backend: value, state: "unknown", can_connect: false, can_disconnect: false })
    refresh()
  }
  function selectProfile(value) {
    if (working || !value.length) return
    profileName = value
    publicIp = ""
    snapshot = ({ backend: backendMode, state: "unknown", can_connect: false, can_disconnect: false })
    refresh()
  }
  function invoke(task) {
    if (working) return
    var args = ["/usr/bin/python3", runner, task, "--backend", backendMode, "--profile", profileName]
    if (task === "connect" || task === "cities") {
      args.push("--country", selectedCountry)
      if (task === "connect" && selectedCity.length) args.push("--city", selectedCity)
    }
    if (task === "countries") discovery = ({ items: [], reason: "Loading countries…" })
    if (task === "cities") cities = ({ items: [], reason: "Loading cities…" })
    if (task === "connect" || task === "disconnect") publicIp = ""
    if (task !== "status") message = ""
    pending = task
    helperExit = -1
    awaiting = true
    process.command = args
    process.running = true
  }
  function finish() {
    if (!awaiting || process.running) return
    var task = pending
    var data
    try { data = JSON.parse(output.text) } catch (e) {
      data = { ok: false, error: "Cannot read the VPN helper response. Refresh, then check Python and the plugin installation." }
    }
    awaiting = false
    pending = ""
    if (!data.ok || helperExit !== 0) {
      message = data.error || "The VPN helper failed. Refresh status before retrying."
      if (task === "countries") discovery = ({ items: [], reason: message })
      else if (task === "cities") cities = ({ items: [], reason: message })
      else if (task !== "ip" || data.code === "disconnected" || data.code === "unconfirmed") {
        snapshot = ({ backend: backendMode, state: "unknown", can_connect: false, can_disconnect: false })
        publicIp = ""
      }
      return
    }
    if (task === "countries") {
      discovery = data
      if (!data.items.some(function(item) { return item.code === root.selectedCountry })) {
        selectedCountry = data.items.some(function(item) { return item.code === "DE" }) ? "DE"
          : data.items.length ? data.items[0].code : ""
        selectedCity = ""
      }
      if (selectedCountry) Qt.callLater(function() { root.invoke("cities") })
    } else if (task === "cities") {
      cities = data
      if (data.items.indexOf(selectedCity) < 0) selectedCity = ""
    } else if (task === "ip") publicIp = data.ip || ""
    else if (data.state !== undefined) {
      if (data.state !== "connected" || snapshot.state !== "connected" || snapshot.device !== data.device) publicIp = ""
      snapshot = data
      message = data.error || ""
      if (task === "check") {
        hasVendor = data.has_vendor === true
        if (dynamicMode && opened && !discovery.items.length)
          Qt.callLater(function() { root.invoke("countries") })
      }
    }
  }

  Process {
    id: process
    stdout: StdioCollector { id: output; waitForEnd: true }
    // Discard stderr; it may contain client/account details.
    onExited: function(exitCode) { root.helperExit = exitCode; Qt.callLater(root.finish) }
    onRunningChanged: if (!running) Qt.callLater(root.finish)
  }
  Timer {
    interval: 15000
    repeat: true
    running: true
    onTriggered: if (!root.working) root.invoke("status")
  }
  Component.onCompleted: refresh()

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
    tooltipText: "CyberGhost VPN · " + root.stateText
    Accessible.name: button.tooltipText
    iconComponent: Component {
      Text {
        textFormat: Text.PlainText
        text: "CG"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.bold: true
        font.pixelSize: Style.font.bodySmall
        font.family: Style.font.family
        color: root.busy ? Color.accent : root.snapshot.state === "connected" ? "#ffcf36" : button.foreground
      }
    }
    onPressed: function(code) { if (code === Qt.LeftButton) root.toggle() }
  }
  Rectangle {
    width: Style.space(4)
    height: width
    radius: width / 2
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    color: root.busy ? Color.accent : root.message ? Color.urgent
      : root.snapshot.state === "connected" ? button.foreground : "transparent"
  }
}
