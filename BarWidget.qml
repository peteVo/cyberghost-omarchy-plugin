pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui as Ui

Ui.BarWidget {
  id: root
  moduleName: "petevo.cyberghost"
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  property var snapshot: ({ backend: "official-cli", state: "unknown", can_connect: false, can_disconnect: false })
  property var trafficSession: null
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
  property var lastSuccessful: setting("lastSuccessful", null)
  property string quickTargetKey: String(setting("quickTargetKey", ""))
  property bool quickConnecting: false
  property bool notifications: setting("notifications", true) === true
  property string observedState: ""
  property double lastStatusAt: 0
  property bool statusFailed: false
  property double verificationAt: 0
  property double publicIpAt: 0
  property double clockNow: Date.now()
  property var versionReport: null
  property var releaseInfo: null
  property double updatesCheckedAt: 0
  // Session intent only: loading the plugin never arms an automatic connection.
  property bool recoveryEnabled: false
  property bool recoveryArmed: false
  property bool recoveryInFlight: false
  property var recoveryTarget: null
  property int recoveryAttempts: 0
  property int recoveryRevision: 0
  property int recoveryIndex: 0
  property bool recoveryKillSwitch: false
  property double recoveryNextAt: 0
  property double recoveryLastClock: 0
  property string recoveryMessage: "Off · Enable before connecting"
  readonly property bool statusStale: lastStatusAt <= 0 || clockNow < lastStatusAt || clockNow - lastStatusAt > 45000
  readonly property var quickTarget: quickTargetKey
    ? favorites.find(function(item) { return root.validTarget(item) && root.favoriteKey(item) === root.quickTargetKey }) || null
    : validTarget(lastSuccessful) ? lastSuccessful : null
  property string publicIp: ""
  property string protectionCheck: ""
  property string diagnosticReport: ""
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
  property bool setupReady: false
  property var setupChecks: []
  property string setupMessage: ""
  property bool killSwitch: setting("killSwitch", false) === true
  readonly property bool busy: awaiting && (pending === "connect" || pending === "recover" || pending === "switch" || pending === "disconnect" || pending === "release-protection")
  readonly property bool working: awaiting
  readonly property bool dynamicMode: backendMode === "official-cli"
  readonly property bool transitioning: busy || snapshot.state === "connecting" || snapshot.state === "disconnecting"
  readonly property bool needsAttention: message.length > 0
    || ["blocked", "recovery-required", "waiting-network"].indexOf(snapshot.state) >= 0
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false
  readonly property string runner: decodeURIComponent(String(Qt.resolvedUrl("cg_bridge.py")).replace(/^file:\/\//, ""))
  readonly property string stateText: busy ? (pending === "release-protection" ? "Restoring networking…" : pending === "disconnect" ? "Disconnecting…" : pending === "switch" ? "Switching…" : pending === "recover" ? "Recovering…" : "Connecting…")
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
  function ageLabel(at) {
    if (!at || clockNow < at) return "Not checked"
    const seconds = Math.floor((clockNow - at) / 1000)
    return seconds < 60 ? seconds + "s ago" : Math.floor(seconds / 60) + "m ago"
  }
  function clearHealth() {
    stopRecovery("Connection settings changed. Enable recovery for the next connection.")
    resetTrafficSession()
    lastStatusAt = 0
    statusFailed = false
    verificationAt = 0
    publicIpAt = 0
    protectionCheck = ""
    observedState = ""
  }
  function validTrafficBytes(value) {
    return typeof value === "number" && isFinite(value) && value >= 0
      && Math.floor(value) === value && value <= 9007199254740991
  }
  function addTrafficBytes(current, increment) {
    if (!validTrafficBytes(current) || !validTrafficBytes(increment)
        || current > 9007199254740991 - increment) return null
    return current + increment
  }
  function resetTrafficSession() { trafficSession = null }
  function observeTraffic(data, task) {
    if (data.state === "disconnected") { resetTrafficSession(); return }
    if (data.state !== "connected") return

    const device = data.device
    const interfaceIndex = data.interface_index
    if (typeof device !== "string" || !device.length || device.length > 15
        || typeof interfaceIndex !== "number" || !isFinite(interfaceIndex)
        || interfaceIndex <= 0 || Math.floor(interfaceIndex) !== interfaceIndex) {
      if (trafficSession) trafficSession = Object.assign({}, trafficSession, { available: false })
      return
    }

    const rawValid = validTrafficBytes(data.download_bytes) && validTrafficBytes(data.upload_bytes)
    const current = task === "connect" ? null : trafficSession
    if (!current) {
      const startedByWidget = task === "connect"
      trafficSession = {
        device: device, interfaceIndex: interfaceIndex,
        downloadBytes: startedByWidget && rawValid ? data.download_bytes : 0,
        uploadBytes: startedByWidget && rawValid ? data.upload_bytes : 0,
        lastDownload: rawValid ? data.download_bytes : null,
        lastUpload: rawValid ? data.upload_bytes : null,
        countNextRaw: startedByWidget && !rawValid,
        available: rawValid
      }
      return
    }

    const sameInterface = current.device === device && current.interfaceIndex === interfaceIndex
    if (!rawValid) {
      trafficSession = sameInterface ? {
        device: current.device, interfaceIndex: current.interfaceIndex,
        downloadBytes: current.downloadBytes, uploadBytes: current.uploadBytes,
        lastDownload: current.lastDownload, lastUpload: current.lastUpload,
        countNextRaw: current.countNextRaw, available: false
      } : {
        device: device, interfaceIndex: interfaceIndex,
        downloadBytes: current.downloadBytes, uploadBytes: current.uploadBytes,
        lastDownload: null, lastUpload: null, countNextRaw: true, available: false
      }
      return
    }

    const downloadIncrement = !sameInterface ? data.download_bytes
      : current.countNextRaw ? data.download_bytes
      : current.lastDownload === null ? 0
      : data.download_bytes >= current.lastDownload ? data.download_bytes - current.lastDownload : data.download_bytes
    const uploadIncrement = !sameInterface ? data.upload_bytes
      : current.countNextRaw ? data.upload_bytes
      : current.lastUpload === null ? 0
      : data.upload_bytes >= current.lastUpload ? data.upload_bytes - current.lastUpload : data.upload_bytes
    const downloadBytes = addTrafficBytes(current.downloadBytes, downloadIncrement)
    const uploadBytes = addTrafficBytes(current.uploadBytes, uploadIncrement)
    trafficSession = {
      device: device, interfaceIndex: interfaceIndex,
      downloadBytes: downloadBytes, uploadBytes: uploadBytes,
      lastDownload: data.download_bytes, lastUpload: data.upload_bytes,
      countNextRaw: false, available: downloadBytes !== null && uploadBytes !== null
    }
  }
  function stopRecovery(reason) {
    recoveryArmed = false
    recoveryInFlight = false
    recoveryTarget = null
    recoveryNextAt = 0
    recoveryRevision++
    recoveryMessage = reason || "Waiting for your next connection"
  }
  function setRecovery(value) {
    recoveryEnabled = value === true
    stopRecovery(recoveryEnabled ? "Enabled for your next WireGuard connection · Up to two attempts" : "Off · Enable before connecting")
  }
  function pauseAutomaticRecovery() { setRecovery(false) }
  function recoverableState(data) {
    return (data.state === "disconnected" && data.can_connect === true
            && data.can_release_protection !== true && !data.error)
      || (data.state === "recovery-required" && data.can_recover === true
          && data.protection_phase === "active" && data.kill_switch === false
          && !recoveryKillSwitch && data.protection_index === recoveryIndex)
  }
  function observeRecovery(data, task) {
    if (!recoveryEnabled) return
    if ((data.error && !recoverableState(data)) || data.other_vpn_active === true) { stopRecovery("Paused · Resolve the connection error before reconnecting"); return }
    if (data.state === "connected" && (data.protocol !== "WireGuard" || data.device !== "cyberghost"
        || typeof data.interface_index !== "number" || !isFinite(data.interface_index)
        || data.interface_index <= 0 || Math.floor(data.interface_index) !== data.interface_index || data.ipv6_guard !== true)) {
      stopRecovery("Recovery needs an identified WireGuard tunnel with recorded protection"); return
    }
    const now = Date.now()
    if (recoveryLastClock && now < recoveryLastClock) { stopRecovery("Paused after clock change. Start a connection again to arm recovery."); return }
    recoveryLastClock = now
    if ((task === "connect" || task === "switch") && data.state === "connected") {
      const target = { country: pendingCountry, city: pendingCity, protocol: selectedProtocol, server: selectedServer }
      if (data.protocol !== "WireGuard" || target.protocol !== "wireguard" || !validTarget(target)) {
        stopRecovery("Recovery requires an explicitly selected WireGuard connection."); return
      }
      recoveryTarget = target
      recoveryIndex = data.interface_index
      recoveryKillSwitch = data.kill_switch === true
      recoveryAttempts = 0
      recoveryArmed = true
      recoveryMessage = "Armed for this connection · No startup connection"
    }
    if (!recoveryArmed) return
    if (data.state === "connected") {
      if (task === "recover") {
        recoveryIndex = data.interface_index
        recoveryInFlight = false
        recoveryMessage = "Recovery completed · Verify connectivity separately"
      } else if (data.interface_index !== recoveryIndex) {
        stopRecovery("Connection changed outside recovery. Start a connection again to arm it.")
      } else if (recoveryNextAt || recoveryMessage.indexOf("Waiting for network") === 0) {
        recoveryNextAt = 0
        recoveryMessage = "Tunnel route returned · Verify connectivity separately"
      }
      return
    }
    if (data.state === "waiting-network" && data.interface_index === recoveryIndex) {
      recoveryNextAt = 0
      recoveryMessage = "Waiting for network · Keeping the existing tunnel"
      return
    }
    if (!recoverableState(data)) {
      stopRecovery("Paused · Connection or traffic protection needs manual attention")
      return
    }
    if (data.uplink_ready !== true) { recoveryMessage = "Waiting for an upstream route"; return }
    if (recoveryAttempts >= 2) { stopRecovery("Two-attempt limit reached · Reconnect manually"); return }
    if (!recoveryNextAt) recoveryNextAt = now + 30000
    recoveryMessage = "Tunnel absent · Waiting before recovery; system authorization may be required"
    if (now < recoveryNextAt) return
    const revision = recoveryRevision
    Qt.callLater(function() {
      if (root.recoveryEnabled && root.recoveryArmed && root.recoveryRevision === revision && !root.working
          && root.recoverableState(root.snapshot) && root.snapshot.uplink_ready === true
          && !root.statusStale && !root.statusFailed) root.invoke("recover")
    })
  }
  function notify(title, body, operation) {
    const peers = bar && typeof bar.moduleWidgets === "function" ? bar.moduleWidgets(moduleName) : [root]
    if (notifications && (operation === true || !peers.length || peers[0] === root))
      Quickshell.execDetached(["/usr/bin/omarchy", "notification", "send", "--app-name", "CyberGhost for Omarchy", title, body])
  }
  function noteStateFailure(silent) {
    statusFailed = true
    verificationAt = 0
    protectionCheck = ""
    if (!silent && observedState && observedState !== "unknown")
      notify("VPN status unavailable", "Open the VPN panel and refresh before relying on the connection.")
    observedState = "unknown"
  }
  function observeState(data, task) {
    clockNow = Date.now()
    observeTraffic(data, task)
    if (data.state === "unknown") noteStateFailure()
    else {
      lastStatusAt = clockNow
      statusFailed = false
      const changed = observedState && observedState !== data.state
      if (task === "connect" || task === "recover" || task === "switch")
        notify(task === "switch" ? "VPN location switched" : "VPN connected", "Connection reported. Check Details for routing and protection observations.", true)
      else if (task === "disconnect" || task === "release-protection")
        notify("VPN disconnected", "Normal networking was requested. Check the panel if recovery needs attention.", true)
      else if (changed && ["waiting-network", "blocked", "recovery-required", "disconnected"].indexOf(data.state) >= 0)
        notify("VPN needs attention", "The connection state changed. Open the VPN panel for recovery options.")
      else if (changed && data.state === "connected")
        notify("VPN connection returned", "Connection reported again. Protection is checked separately.")
      observedState = data.state
    }
    if ((task === "connect" || task === "switch") && data.state === "connected" && dynamicMode) {
      const target = { country: pendingCountry, city: pendingCity, protocol: selectedProtocol, server: selectedServer }
      if (validTarget(target)) { lastSuccessful = target; persistSettings({ lastSuccessful: target }) }
    }
    observeRecovery(data, task)
  }
  function validTarget(item) {
    return !!item && typeof item === "object" && !Array.isArray(item)
      && typeof item.country === "string" && /^[A-Z]{2}$/.test(item.country)
      && ["auto", "wireguard", "openvpn"].indexOf(item.protocol) >= 0
      && (item.city === undefined || (typeof item.city === "string" && item.city.length <= 64))
      && (item.server === undefined || (typeof item.server === "string" && (!item.server || (item.city && /^[a-z0-9][a-z0-9-]{0,63}$/.test(item.server)))))
  }
  function cancelSavedTarget() { favoriteToApply = null; quickConnecting = false }
  function cancelQuickConnect() {
    stopRecovery("Quick Connect cancelled")
    selectionRevision++
    cancelSavedTarget()
    message = "Quick Connect cancelled before connecting."
  }
  function startSavedTarget(target, connectAfter) {
    if (working || protocolRefresh || !dynamicMode) return
    stopRecovery("Saved target changed. Start a connection to arm recovery.")
    if (!validTarget(target)) {
      message = "This saved location has invalid settings. Remove it and save the location again."
      cancelSavedTarget()
      return
    }
    favoriteToApply = { country: target.country, city: target.city || "", protocol: target.protocol, server: target.server || "" }
    quickConnecting = connectAfter === true
    selectedCountry = target.country
    selectedProtocol = target.protocol
    resetLocations()
    selectionRevision++
    discovery = ({ items: [], reason: "Checking saved country…" })
    persistSettings({ protocol: selectedProtocol })
    invoke("countries")
  }
  function quickConnect() {
    if (working || protocolRefresh || !setupReady || !dynamicMode || snapshot.state !== "disconnected" || snapshot.can_connect !== true) return
    if (!quickTarget) { message = "Choose a favorite for Quick Connect or connect to a location once."; return }
    if (killSwitch && quickTarget.protocol !== "wireguard") {
      message = "Quick Connect needs a WireGuard location while the kill switch is selected."
      return
    }
    startSavedTarget(quickTarget, true)
  }
  function completeSavedTarget() {
    const connectAfter = quickConnecting
    const revision = selectionRevision
    cancelSavedTarget()
    if (connectAfter) Qt.callLater(function() {
      if (root.selectionRevision === revision && !root.working && root.setupReady
          && root.snapshot.state === "disconnected" && root.snapshot.can_connect === true)
        root.invoke("connect")
    })
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
    setupReady = false
    setupChecks = []
    setupMessage = "Checking local setup…"
    diagnosticReport = ""
    clearHealth()
    persistSettings({ backend: value })
    selectedCountry = ""
    resetLocations()
    discovery = ({ items: [], reason: "" })
    cancelSavedTarget()
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
    clearHealth()
    cancelSavedTarget()
    selectionRevision++
    snapshot = ({ backend: backendMode, state: "unknown", can_connect: false, can_disconnect: false })
    refresh()
  }
  function selectCountry(value) {
    if (working || protocolRefresh || value === selectedCountry) return
    stopRecovery("Selected location changed. Start a connection to arm recovery.")
    cancelSavedTarget()
    selectedCountry = value
    resetLocations()
    selectionRevision++
    if (value) invoke("cities")
  }
  function selectCity(value) {
    if (working || protocolRefresh || value === selectedCity) return
    stopRecovery("Selected location changed. Start a connection to arm recovery.")
    cancelSavedTarget()
    selectedCity = value
    selectedServer = ""
    servers = ({ items: [], reason: value ? "Loading servers…" : "Choose a city to browse individual servers." })
    selectionRevision++
    if (value) invoke("servers")
  }
  function selectServer(value) {
    if (working || protocolRefresh || value === selectedServer) return
    stopRecovery("Selected server changed. Start a connection to arm recovery.")
    cancelSavedTarget()
    selectedServer = value
    selectionRevision++
  }
  function selectProtocol(value) {
    if (working || protocolRefresh || ["auto", "wireguard", "openvpn"].indexOf(value) < 0 || value === selectedProtocol) return
    stopRecovery("Protocol changed. Start a connection to arm recovery.")
    cancelSavedTarget()
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
    stopRecovery("Protection preference changed. Start a connection to arm recovery.")
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
      cancelSavedTarget()
      selectionRevision++
    }
    var next = favorites.slice()
    next.splice(index, 1)
    favorites = next
    persistSettings({ favorites: next })
  }
  function applyFavorite(index) {
    if (working || protocolRefresh || index < 0 || index >= favorites.length) return
    startSavedTarget(favorites[index], false)
  }
  function invoke(task) {
    if (working) return
    if (task === "connect") resetTrafficSession()
    if (["connect", "switch", "disconnect", "release-protection"].indexOf(task) >= 0) stopRecovery("Manual operation · Automatic attempts cancelled")
    if (task === "recover") {
      if (!recoveryEnabled || !recoveryArmed || recoveryAttempts >= 2 || !validTarget(recoveryTarget)
          || recoveryTarget.protocol !== "wireguard" || !recoverableState(snapshot)
          || snapshot.uplink_ready !== true
          || statusStale || statusFailed || !setupReady || !dynamicMode) return
      recoveryAttempts++
      recoveryInFlight = true
      recoveryNextAt = 0
      recoveryMessage = "Recovery attempt " + recoveryAttempts + " of 2 · Authorization may be required"
    }
    const target = task === "recover" ? recoveryTarget : { country: selectedCountry, city: selectedCity, protocol: selectedProtocol, server: selectedServer }
    var args = ["/usr/bin/python3", runner, task === "recover" ? (snapshot.can_recover === true ? "recover" : "connect") : task, "--backend", backendMode, "--profile", profileName]
    if (["countries", "cities", "servers", "connect", "recover", "switch"].indexOf(task) >= 0) args.push("--protocol", target.protocol)
    if (["cities", "servers", "connect", "recover", "switch"].indexOf(task) >= 0) args.push("--country", target.country)
    if (["servers", "connect", "recover", "switch"].indexOf(task) >= 0) {
      if (target.city.length) args.push("--city", target.city)
      args.push("--server", target.server)
    }
    if ((task === "connect" || task === "recover" || task === "switch") && dynamicMode
        && (task === "recover" ? recoveryKillSwitch : killSwitch)) args.push("--kill-switch")
    if (task === "countries") discovery = ({ items: [], reason: "Loading countries…" })
    if (task === "cities") cities = ({ items: [], reason: "Loading cities…" })
    if (task === "servers") servers = ({ items: [], reason: "Loading servers…" })
    if (task === "connect" || task === "recover" || task === "switch" || task === "disconnect" || task === "release-protection") {
      publicIp = ""
      protectionCheck = ""
      publicIpAt = 0
      verificationAt = 0
    }
    if (task === "verify-protection") { verificationAt = 0; protectionCheck = "" }
    if (task !== "status") message = ""
    pending = task
    pendingCountry = target.country
    pendingCity = target.city
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
      if (data.ok && (task === "countries" || task === "cities" || task === "servers")) {
        if (!Array.isArray(data.items)) throw new Error("Invalid location list")
        if (data.items.some(function(item) {
          return task === "cities" ? typeof item !== "string"
            : !item || typeof item !== "object" || typeof item.name !== "string"
              || (task === "countries" && typeof item.code !== "string")
        })) throw new Error("Invalid location entry")
      }
      if (data.ok && task === "check" && (!Array.isArray(data.prerequisites)
          || typeof data.setup_ready !== "boolean"
          || data.prerequisites.some(function(item) {
            return !item || typeof item !== "object" || typeof item.ready !== "boolean"
              || typeof item.label !== "string" || typeof item.message !== "string"
          }))) throw new Error("Invalid setup checks")
      if (data.ok && ["check", "status", "connect", "recover", "switch", "disconnect", "release-protection"].indexOf(task) >= 0
          && (["unknown", "connected", "disconnected", "connecting", "disconnecting", "waiting-network", "blocked", "recovery-required"].indexOf(data.state) < 0
              || typeof data.can_connect !== "boolean" || typeof data.can_disconnect !== "boolean"))
        throw new Error("Invalid connection state")
      if (data.ok && task === "ip" && (typeof data.ip !== "string" || !data.ip.length))
        throw new Error("Invalid IP result")
      if (data.ok && task === "verify-protection" && typeof data.protection_verified !== "boolean")
        throw new Error("Invalid protection result")
      if (data.ok && (task === "diagnostics" || (task === "check" && data.report !== undefined)) && (!data.report || typeof data.report !== "object"
          || Array.isArray(data.report) || data.report.schema !== 1 || typeof data.report.plugin_version !== "string"
          || (data.report.plugin_version !== "unknown" && !/^[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?$/.test(data.report.plugin_version))
          || typeof data.report.python_version !== "string" || !/^[0-9]+\.[0-9]+\.[0-9]+$/.test(data.report.python_version)
          || ["linux", "unsupported"].indexOf(data.report.platform) < 0 || data.report.backend !== backendMode
          || (data.report.helper_api !== null && [4, 5, 6].indexOf(data.report.helper_api) < 0)
          || Object.keys(data.report).some(function(key) { return ["schema", "plugin_version", "python_version", "helper_api", "platform", "backend", "packages", "prerequisites"].indexOf(key) < 0 })
          || !Array.isArray(data.report.prerequisites) || data.report.prerequisites.some(function(item) {
            return !item || typeof item.ready !== "boolean"
              || ["python", "architecture", "tools", "NetworkManager", "systemd-resolved", "resolvconf", "adapter", "resolver"].indexOf(item.id) < 0
              || Object.keys(item).some(function(key) { return key !== "id" && key !== "ready" })
          }) || !data.report.packages || typeof data.report.packages !== "object" || Array.isArray(data.report.packages)
          || Object.keys(data.report.packages).some(function(key) {
            const value = data.report.packages[key]
            return ["omarchy", "quickshell", "networkmanager", "systemd", "cyberghostvpn-omarchy", "cyberghostvpn"].indexOf(key) < 0
              || (value !== null && (typeof value !== "string" || !/^[0-9][A-Za-z0-9.+_:~\-]{0,63}$/.test(value)))
          })))
        throw new Error("Invalid diagnostic report")
      if (data.ok && task === "updates" && data.release !== null && (!data.release || typeof data.release !== "object"
          || typeof data.release.tag !== "string" || !/^v[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:-beta\.[0-9]{1,4})?$/.test(data.release.tag)
          || typeof data.release.prerelease !== "boolean"
          || data.release.url !== "https://github.com/peteVo/cyberghost-omarchy-plugin/releases/tag/" + data.release.tag))
        throw new Error("Invalid release information")
    } catch (e) {
      data = { ok: false, error: "Cannot read the VPN helper response. Refresh, then check Python and the plugin installation." }
    }
    awaiting = false
    pending = ""
    // Bar settings can arrive after the initial helper was started.
    if ((data.backend !== undefined && data.backend !== backendMode)
        || (data.profile !== undefined && data.profile !== profileName)) {
      stopRecovery("Backend changed · Automatic recovery paused")
      Qt.callLater(root.refresh)
      return
    }
    if (!data.ok || helperExit !== 0) {
      message = data.error || "The VPN helper failed. Refresh status before retrying."
      if (task === "countries") discovery = ({ items: [], reason: message })
      else if (task === "cities") cities = ({ items: [], reason: message })
      else if (task === "servers") servers = ({ items: [], reason: message })
      else if (task !== "diagnostics" && task !== "updates" && (task !== "ip" || data.code === "disconnected" || data.code === "unconfirmed")) {
        snapshot = ({ backend: backendMode, state: "unknown", can_connect: false, can_disconnect: false })
        publicIp = ""
      }
      if (task === "countries" || task === "cities" || task === "servers") cancelSavedTarget()
      if (["status", "check", "connect", "recover", "switch", "disconnect", "release-protection"].indexOf(task) >= 0) {
        const operation = ["connect", "recover", "switch", "disconnect", "release-protection"].indexOf(task) >= 0
        noteStateFailure(operation)
        if (operation)
          notify("VPN operation needs attention", "Open the VPN panel for the error and recovery options.", true)
      }
      if (task === "recover") {
        recoveryInFlight = false
        if (data.code !== "operation_failed" || recoveryAttempts >= 2) stopRecovery("Recovery stopped · Check the error and reconnect manually")
        else { recoveryNextAt = Date.now() + 60000; recoveryMessage = "Attempt failed · Waiting for fresh safe status before the final retry" }
      } else if (task === "status" || task === "check") stopRecovery("Status unavailable · Automatic recovery paused")
      if (task === "countries" || task === "cities") protocolRefresh = false
      if (task === "check") { setupReady = false; setupMessage = message }
      if (task === "diagnostics") diagnosticReport = ""
      if (task === "updates") { releaseInfo = null; updatesCheckedAt = 0 }
      if (task === "verify-protection") { verificationAt = 0; protectionCheck = "" }
      if (panelLoader.item) panelLoader.item.revealMessage()
      return
    }
    clockNow = Date.now()
    if (task === "countries") {
      if (pendingRevision !== selectionRevision) return
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
          cancelSavedTarget()
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
          cancelSavedTarget()
          message = "The saved city is no longer available. Choose a discovered city or remove the favorite."
          return
        }
        selectedCity = favoriteToApply.city || ""
      } else if (data.items.indexOf(selectedCity) < 0) {
        selectedCity = ""
        selectedServer = ""
      }
      if (selectedCity) invoke("servers")
      else if (favoriteToApply) completeSavedTarget()
    } else if (task === "servers") {
      if (pendingCountry !== selectedCountry || pendingCity !== selectedCity || pendingRevision !== selectionRevision) return
      servers = data
      if (favoriteToApply) {
        if (favoriteToApply.server && !data.items.some(function(item) { return item.name === favoriteToApply.server })) {
          cancelSavedTarget()
          message = "The saved server is no longer available. Choose a discovered server or remove the favorite."
          return
        }
        selectedServer = favoriteToApply.server || ""
        completeSavedTarget()
      } else if (selectedServer && !data.items.some(function(item) { return item.name === selectedServer })) selectedServer = ""
    } else if (task === "diagnostics") {
      versionReport = data.report
      diagnosticReport = JSON.stringify(data.report, null, 2)
      if (panelLoader.item) panelLoader.item.revealReport()
    }
    else if (task === "updates") {
      releaseInfo = data.release
      updatesCheckedAt = clockNow
      if (panelLoader.item) panelLoader.item.revealUpdates()
    }
    else if (task === "ip") { publicIp = data.ip || ""; publicIpAt = clockNow }
    else if (task === "verify-protection") {
      verificationAt = clockNow
      protectionCheck = data.protection_verified === true ? "Last check: rules and tunnel matched."
        : "Last check failed. Disconnect and reconnect before relying on protection."
      if (data.protection_verified !== true) message = protectionCheck
    }
    else if (data.state !== undefined) {
      if (data.state !== "connected" || snapshot.state !== "connected" || snapshot.device !== data.device || snapshot.interface_index !== data.interface_index) {
        publicIp = ""
        protectionCheck = ""
        publicIpAt = 0
        verificationAt = 0
      }
      observeState(data, task)
      snapshot = data
      message = data.error || data.warning || ""
      if (message && panelLoader.item) panelLoader.item.revealMessage()
      if (task === "check") {
        if (data.report) versionReport = data.report
        hasVendor = data.has_vendor === true
        setupReady = data.setup_ready === true
        setupChecks = arrayFrom(data.prerequisites)
        setupMessage = String(data.setup_message || "")
        if (dynamicMode && opened && !discovery.items.length)
          Qt.callLater(function() { root.invoke("countries") })
      }
    }
  }

  IpcHandler {
    target: "petevo.cyberghost"
    function pauseRecovery(): string {
      root.broadcast("pauseAutomaticRecovery")
      return "paused"
    }
    function diagnostics(): string {
      const origin = button.mapToGlobal(0, 0)
      return JSON.stringify({ opened: root.opened,
        icon: { x: origin.x, y: origin.y, width: button.width, height: button.height },
        focused: panelLoader.item ? panelLoader.item.panelFocused === true : false,
        focusControl: panelLoader.item ? panelLoader.item.focusControl : "",
        focusRect: panelLoader.item ? panelLoader.item.focusRect : null,
        panelRect: panelLoader.item ? panelLoader.item.panelBounds() : null,
        search: panelLoader.item ? panelLoader.item.searchPlaceholder : "",
        section: panelLoader.item ? panelLoader.item.section : "",
        working: root.working, pending: root.pending, state: root.snapshot.state,
        backend: root.backendMode, country: root.selectedCountry, city: root.selectedCity,
        protocol: root.selectedProtocol, server: root.selectedServer,
        killSwitch: root.killSwitch, configuredKillSwitch: root.snapshot.kill_switch === true,
        ipv6Guard: root.snapshot.ipv6_guard === true,
        setupReady: root.setupReady, setupChecks: root.setupChecks.length,
        statusStale: root.statusStale, statusFailed: root.statusFailed,
        statusChecked: root.lastStatusAt > 0, verificationChecked: root.verificationAt > 0,
        quickConnecting: root.quickConnecting, quickTargetReady: !!root.quickTarget,
        recoveryEnabled: root.recoveryEnabled, recoveryArmed: root.recoveryArmed,
        recoveryAttempts: root.recoveryAttempts, recoveryInFlight: root.recoveryInFlight,
        versionsReady: !!root.versionReport, updatesChecked: root.updatesCheckedAt > 0,
        canSwitch: panelLoader.item ? panelLoader.item.canSwitch : false,
        notificationsEnabled: root.notifications, lastSuccessfulSaved: root.validTarget(root.lastSuccessful),
        reportReady: root.diagnosticReport.length > 0,
        reportSelected: panelLoader.item ? panelLoader.item.reportSelected : false,
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
    interval: 1000
    repeat: true
    running: root.opened
    onTriggered: root.clockNow = Date.now()
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
      GhostIcon {
        anchors.centerIn: parent
        opticalScale: 0.8
        color: root.transitioning ? Color.accent : root.needsAttention ? Color.urgent
          : root.snapshot.state === "connected" ? (button.foreground.r + button.foreground.g + button.foreground.b < 1.5 ? "#866200" : "#ffcf36") : button.foreground
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
