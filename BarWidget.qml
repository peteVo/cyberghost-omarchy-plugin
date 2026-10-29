pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Shapes
import Quickshell.Io
import qs.Commons
import qs.Ui as Ui

Ui.BarWidget {
  id: root
  moduleName: "petevo.cyberghost"
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  property var snapshot: ({ backend: "official-cli", state: "unknown", can_connect: false, can_disconnect: false })
  property var discovery: ({ items: [], reason: "" })
  property var cities: ({ items: [], reason: "" })
  property var servers: ({ items: [], reason: "" })
  property var favorites: arrayFrom(setting("favorites", []))
  property string backendMode: String(setting("backend", "official-cli"))
  property string profileName: String(setting("profile", "cyberghost"))
  property string selectedCountry: ""
  property string selectedCity: ""
  property string selectedProtocol: ["auto", "wireguard", "openvpn"].indexOf(String(setting("protocol", "wireguard"))) >= 0
    ? String(setting("protocol", "wireguard")) : "wireguard"
  property string selectedServer: ""
  property var favoriteToApply: null
  property string publicIp: ""
  property string protectionCheck: ""
  property string message: ""
  property string pending: ""
  property string pendingCountry: ""
  property string pendingCity: ""
  property int selectionRevision: 0
  property int pendingRevision: -1
  property bool protocolRefresh: false
  property bool awaiting: false
  property int helperExit: -1
  property bool hasVendor: false
  property bool killSwitch: setting("killSwitch", false) === true
  readonly property bool busy: awaiting && (pending === "connect" || pending === "switch" || pending === "disconnect" || pending === "release-protection")
  readonly property bool working: awaiting
  readonly property bool dynamicMode: backendMode === "official-cli"
  readonly property bool transitioning: busy || snapshot.state === "connecting" || snapshot.state === "disconnecting"
  readonly property bool needsAttention: message.length > 0
    || ["blocked", "recovery-required", "waiting-network"].indexOf(snapshot.state) >= 0
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false
  readonly property string runner: decodeURIComponent(String(Qt.resolvedUrl("cg_bridge.py")).replace(/^file:\/\//, ""))
  readonly property string stateText: busy ? (pending === "release-protection" ? "Restoring networking…" : pending === "disconnect" ? "Disconnecting…" : pending === "switch" ? "Switching…" : "Connecting…")
    : snapshot.other_vpn_active === true ? "Another VPN active"
    : snapshot.state === "connected" ? "Connected"
    : snapshot.state === "disconnected" ? "Disconnected"
    : snapshot.state === "waiting-network" ? "Waiting for network…"
    : snapshot.state === "blocked" ? "Traffic block configured"
    : snapshot.state === "recovery-required" ? "Recovery required"
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
    if (!working && !protocolRefresh) invoke("check")
  }
  function arrayFrom(value) {
    if (!value || typeof value.length !== "number" || typeof value === "string") return []
    var result = []
    for (var i = 0; i < value.length; i++) result.push(value[i])
    return result
  }
  function persistSettings(values) {
    var entry = { id: moduleName }
    for (var key in settings) if (key !== "id") entry[key] = settings[key]
    for (var name in values) entry[name] = values[name]
    settings = entry
    if (bar && bar.shell && typeof bar.shell.updateEntryInline === "function")
      bar.shell.updateEntryInline(moduleName, entry)
  }
  function resetLocations() {
    cities = ({ items: [], reason: "" })
    servers = ({ items: [], reason: "" })
    selectedCity = ""
    selectedServer = ""
  }
  function selectBackend(value) {
    if (working || value === backendMode) return
    backendMode = value
    persistSettings({ backend: value })
    selectedCountry = ""
    resetLocations()
    discovery = ({ items: [], reason: "" })
    favoriteToApply = null
    protocolRefresh = false
    selectionRevision++
    publicIp = ""
    snapshot = ({ backend: value, state: "unknown", can_connect: false, can_disconnect: false })
    refresh()
  }
  function selectProfile(value) {
    if (working || !value.length) return
    profileName = value
    persistSettings({ profile: value })
    publicIp = ""
    snapshot = ({ backend: backendMode, state: "unknown", can_connect: false, can_disconnect: false })
    refresh()
  }
  function selectCountry(value) {
    if (working || protocolRefresh || value === selectedCountry) return
    favoriteToApply = null
    selectedCountry = value
    resetLocations()
    selectionRevision++
    if (value) invoke("cities")
  }
  function selectCity(value) {
    if (working || protocolRefresh || value === selectedCity) return
    favoriteToApply = null
    selectedCity = value
    selectedServer = ""
    servers = ({ items: [], reason: value ? "Loading servers…" : "Choose a city to browse individual servers." })
    selectionRevision++
    if (value) invoke("servers")
  }
  function selectProtocol(value) {
    if (working || protocolRefresh || ["auto", "wireguard", "openvpn"].indexOf(value) < 0 || value === selectedProtocol) return
    favoriteToApply = null
    selectedProtocol = value
    selectedServer = ""
    cities = ({ items: [], reason: "Checking cities for selected protocol…" })
    servers = ({ items: [], reason: "Checking servers for selected protocol…" })
    protocolRefresh = true
    selectionRevision++
    persistSettings({ protocol: value })
    invoke("countries")
  }
  function setKillSwitch(value) {
    if (working || snapshot.can_disconnect) return
    killSwitch = value === true
    persistSettings({ killSwitch: killSwitch })
  }
  function favoriteKey(item) {
    if (!item || typeof item !== "object") return ""
    return JSON.stringify([item.country, item.city || "", item.protocol, item.server || ""])
  }
  function saveFavorite() {
    if (working || protocolRefresh || favoriteToApply || !discovery.items.some(function(item) { return item.code === selectedCountry })
        || (selectedCity && cities.items.indexOf(selectedCity) < 0)
        || (selectedServer && !servers.items.some(function(item) { return item.name === selectedServer }))) return
    var favorite = { country: selectedCountry, city: selectedCity, protocol: selectedProtocol, server: selectedServer }
    var next = favorites.slice()
    if (next.some(function(item) { return favoriteKey(item) === favoriteKey(favorite) })) return
    next.push(favorite)
    favorites = next
    persistSettings({ favorites: next })
  }
  function removeFavorite(index) {
    if (working || index < 0 || index >= favorites.length) return
    if (favoriteToApply && favoriteKey(favoriteToApply) === favoriteKey(favorites[index])) {
      favoriteToApply = null
      selectionRevision++
    }
    var next = favorites.slice()
    next.splice(index, 1)
    favorites = next
    persistSettings({ favorites: next })
  }
  function applyFavorite(index) {
    if (working || protocolRefresh || index < 0 || index >= favorites.length) return
    var favorite = favorites[index]
    if (!favorite || ["auto", "wireguard", "openvpn"].indexOf(favorite.protocol) < 0) {
      message = "This saved location has invalid settings. Remove it and save the location again."
      return
    }
    favoriteToApply = favorite
    selectedCountry = String(favorite.country || "")
    selectedCity = ""
    selectedServer = ""
    selectedProtocol = favorite.protocol
    selectionRevision++
    discovery = ({ items: [], reason: "Checking saved country…" })
    resetLocations()
    persistSettings({ protocol: selectedProtocol })
    invoke("countries")
  }
  function invoke(task) {
    if (working) return
    var args = ["/usr/bin/python3", runner, task, "--backend", backendMode, "--profile", profileName]
    if (task === "countries" || task === "cities" || task === "servers" || task === "connect" || task === "switch")
      args.push("--protocol", selectedProtocol)
    if (task === "cities" || task === "servers" || task === "connect" || task === "switch") {
      args.push("--country", selectedCountry)
      if ((task === "servers" || task === "connect" || task === "switch") && selectedCity.length)
        args.push("--city", selectedCity)
    }
    if (task === "servers" || task === "connect" || task === "switch") args.push("--server", selectedServer)
    if ((task === "connect" || task === "switch") && dynamicMode && killSwitch) args.push("--kill-switch")
    if (task === "countries") discovery = ({ items: [], reason: "Loading countries…" })
    if (task === "cities") cities = ({ items: [], reason: "Loading cities…" })
    if (task === "servers") servers = ({ items: [], reason: "Loading servers…" })
    if (task === "connect" || task === "switch" || task === "disconnect" || task === "release-protection") {
      publicIp = ""
      protectionCheck = ""
    }
    if (task !== "status") message = ""
    pending = task
    pendingCountry = selectedCountry
    pendingCity = selectedCity
    pendingRevision = selectionRevision
    helperExit = -1
    awaiting = true
    process.command = args
    process.running = true
  }
  function finish() {
    if (!awaiting || process.running) return
    var task = pending
    var data
    try {
      data = JSON.parse(output.text)
      if (!data || typeof data !== "object" || Array.isArray(data) || typeof data.ok !== "boolean")
        throw new Error("Invalid response object")
    } catch (e) {
      data = { ok: false, error: "Cannot read the VPN helper response. Refresh, then check Python and the plugin installation." }
    }
    awaiting = false
    pending = ""
    // Bar settings can arrive after the initial helper was started.
    if ((data.backend !== undefined && data.backend !== backendMode)
        || (data.profile !== undefined && data.profile !== profileName)) {
      Qt.callLater(root.refresh)
      return
    }
    if (!data.ok || helperExit !== 0) {
      message = data.error || "The VPN helper failed. Refresh status before retrying."
      if (task === "countries") discovery = ({ items: [], reason: message })
      else if (task === "cities") cities = ({ items: [], reason: message })
      else if (task === "servers") servers = ({ items: [], reason: message })
      else if (task !== "ip" || data.code === "disconnected" || data.code === "unconfirmed") {
        snapshot = ({ backend: backendMode, state: "unknown", can_connect: false, can_disconnect: false })
        publicIp = ""
      }
      if (task === "countries" || task === "cities" || task === "servers") favoriteToApply = null
      if (task === "countries" || task === "cities") protocolRefresh = false
      return
    }
    if (task === "countries") {
      discovery = data
      if (protocolRefresh && !selectedCountry) {
        protocolRefresh = false
        cities = ({ items: [], reason: "" })
        servers = ({ items: [], reason: "Choose a city to browse individual servers." })
        return
      }
      if (protocolRefresh && !data.items.some(function(item) { return item.code === root.selectedCountry })) {
        selectedCountry = ""
        resetLocations()
        protocolRefresh = false
        message = "The selected country is unavailable with this protocol. Choose a discovered country."
        return
      }
      if (favoriteToApply) {
        if (!data.items.some(function(item) { return item.code === favoriteToApply.country })) {
          favoriteToApply = null
          message = "The saved country is no longer available. Choose a discovered country or remove the favorite."
          return
        }
        selectedCountry = favoriteToApply.country
      } else if (!data.items.some(function(item) { return item.code === root.selectedCountry })) {
        selectedCountry = data.items.some(function(item) { return item.code === "DE" }) ? "DE"
          : data.items.length ? data.items[0].code : ""
        resetLocations()
      }
      if (selectedCountry) {
        var country = selectedCountry
        var revision = selectionRevision
        Qt.callLater(function() {
          if (root.selectedCountry === country && root.selectionRevision === revision) root.invoke("cities")
        })
      }
    } else if (task === "cities") {
      if (pendingCountry !== selectedCountry || pendingRevision !== selectionRevision) return
      cities = data
      if (protocolRefresh) {
        if (selectedCity && data.items.indexOf(selectedCity) < 0) {
          selectedCity = ""
          selectedServer = ""
          message = "The selected city is unavailable with this protocol. Choose another city or Any city."
        }
        protocolRefresh = false
        if (!selectedCity) servers = ({ items: [], reason: "Choose a city to browse individual servers." })
      }
      if (favoriteToApply) {
        if (favoriteToApply.city && data.items.indexOf(favoriteToApply.city) < 0) {
          favoriteToApply = null
          message = "The saved city is no longer available. Choose a discovered city or remove the favorite."
          return
        }
        selectedCity = favoriteToApply.city || ""
      } else if (data.items.indexOf(selectedCity) < 0) {
        selectedCity = ""
        selectedServer = ""
      }
      if (selectedCity) invoke("servers")
      else if (favoriteToApply) favoriteToApply = null
    } else if (task === "servers") {
      if (pendingCountry !== selectedCountry || pendingCity !== selectedCity || pendingRevision !== selectionRevision) return
      servers = data
      if (favoriteToApply) {
        if (favoriteToApply.server && !data.items.some(function(item) { return item.name === favoriteToApply.server })) {
          favoriteToApply = null
          message = "The saved server is no longer available. Choose a discovered server or remove the favorite."
          return
        }
        selectedServer = favoriteToApply.server || ""
        favoriteToApply = null
      } else if (selectedServer && !data.items.some(function(item) { return item.name === selectedServer })) selectedServer = ""
    } else if (task === "ip") publicIp = data.ip || ""
    else if (task === "verify-protection") {
      protectionCheck = data.protection_verified === true ? "Last check: rules and tunnel matched."
        : "Last check failed. Disconnect and reconnect before relying on protection."
      if (data.protection_verified !== true) message = protectionCheck
    }
    else if (data.state !== undefined) {
      if (data.state !== "connected" || snapshot.state !== "connected" || snapshot.device !== data.device || snapshot.interface_index !== data.interface_index) {
        publicIp = ""
        protectionCheck = ""
      }
      snapshot = data
      message = data.error || data.warning || ""
      if (task === "check") {
        hasVendor = data.has_vendor === true
        if (dynamicMode && opened && !discovery.items.length)
          Qt.callLater(function() { root.invoke("countries") })
      }
    }
  }

  IpcHandler {
    target: "petevo.cyberghost"
    function diagnostics(): string {
      const origin = button.mapToGlobal(0, 0)
      return JSON.stringify({ opened: root.opened,
        icon: { x: origin.x, y: origin.y, width: button.width, height: button.height },
        focused: panelLoader.item ? panelLoader.item.panelFocused === true : false,
        focusControl: panelLoader.item ? panelLoader.item.focusControl : "",
        focusRect: panelLoader.item ? panelLoader.item.focusRect : null,
        search: panelLoader.item ? panelLoader.item.searchPlaceholder : "",
        section: panelLoader.item ? panelLoader.item.section : "",
        working: root.working, pending: root.pending, state: root.snapshot.state,
        backend: root.backendMode, country: root.selectedCountry, city: root.selectedCity,
        protocol: root.selectedProtocol, server: root.selectedServer,
        killSwitch: root.killSwitch, configuredKillSwitch: root.snapshot.kill_switch === true,
        ipv6Guard: root.snapshot.ipv6_guard === true,
        favorites: root.favorites.length, hasIp: root.publicIp.length > 0, message: root.message })
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
    onTriggered: if (!root.working && !root.protocolRefresh) root.invoke("status")
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
      Shape {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -Style.space(1)
        width: 20
        height: 20
        scale: Math.min(parent.width, parent.height) / 20 * 0.8
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
          strokeWidth: 0
          fillRule: ShapePath.OddEvenFill
          fillColor: root.transitioning ? Color.accent : root.needsAttention ? Color.urgent
            : root.snapshot.state === "connected" ? (button.foreground.r + button.foreground.g + button.foreground.b < 1.5 ? "#866200" : "#ffcf36") : button.foreground
          PathSvg {
            path: "M3 17.5V8.5a7 7 0 0 1 14 0v9q0 1.6-1.4.5L13 16.5l-2 2q-1 1-2 0l-2-2-2.6 2Q3 19.1 3 17.5Z M8.6 9.5a1.1 1.6 0 1 1-2.2 0a1.1 1.6 0 1 1 2.2 0Z M13.6 9.5a1.1 1.6 0 1 1-2.2 0a1.1 1.6 0 1 1 2.2 0Z"
          }
        }
      }
    }
    onPressed: function(code) { if (code === Qt.LeftButton) root.toggle() }
  }
  Rectangle {
    width: Style.space(4)
    height: width
    radius: root.needsAttention && !root.transitioning ? 0 : width / 2
    rotation: root.needsAttention && !root.transitioning ? 45 : 0
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    anchors.rightMargin: Style.space(1)
    anchors.bottomMargin: Style.space(1)
    color: root.transitioning ? "transparent" : root.needsAttention ? Color.urgent
      : root.snapshot.state === "connected" ? button.foreground : "transparent"
    border.width: root.transitioning ? 1 : 0
    border.color: Color.accent
  }
}
