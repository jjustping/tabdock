// TabDock.app — runs the TabDock server and shows its icon in the menu bar.
//
// 1. Owns macOS privacy permissions (Full Disk Access, removable volumes, Calendar, Automation): the server
//    is started as a child process, so macOS attributes its file access to "TabDock", not to an anonymous Python.
// 2. Menu-bar icon: status, address, connected devices, autostart at login, QR code, restart, log, stop.
//
//   TabDock.app/Contents/MacOS/TabDock <python> <server.py> [args...]
import AppKit
import WebKit
import Foundation

let LABEL = "com.jjustping.tabdock"
let serverArgs = Array(CommandLine.arguments.dropFirst())
guard serverArgs.count >= 2 else {
    FileHandle.standardError.write("usage: TabDock <python> <server.py> [args]\n".data(using: .utf8)!)
    exit(2)
}
let port: Int = {
    if let i = serverArgs.firstIndex(of: "--port"), i + 1 < serverArgs.count, let p = Int(serverArgs[i + 1]) { return p }
    return 8787
}()
let uid = getuid()
let logDir = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/TabDock")

// ---------------- the server process ----------------
final class Server {
    private(set) var pid: pid_t = 0
    var intentional = false          // restart / stop asked from the menu: don't treat the exit as a crash

    func start() {
        var p: pid_t = 0
        var cargs: [UnsafeMutablePointer<CChar>?] = serverArgs.map { strdup($0) } + [nil]
        let rc = posix_spawn(&p, serverArgs[0], nil, nil, &cargs, environ)
        if rc != 0 {
            FileHandle.standardError.write("TabDock: cannot start \(serverArgs[0]): \(String(cString: strerror(rc)))\n".data(using: .utf8)!)
            exit(1)
        }
        pid = p
        let watched = p
        DispatchQueue.global().async { [weak self] in
            var status: Int32 = 0
            waitpid(watched, &status, 0)
            DispatchQueue.main.async {
                guard let self = self, self.pid == watched else { return }
                if self.intentional { return }
                // the server died on its own: exit with its code so launchd restarts the whole app
                exit((status & 0x7f) == 0 ? (status >> 8) & 0xff : 1)
            }
        }
    }

    func stop(then: @escaping () -> Void) {
        intentional = true
        let p = pid
        kill(p, SIGTERM)
        DispatchQueue.global().async {
            for _ in 0..<50 { if kill(p, 0) != 0 { break }; usleep(100_000) }
            if kill(p, 0) == 0 { kill(p, SIGKILL) }
            DispatchQueue.main.async { then() }
        }
    }

    func restart() { stop { self.intentional = false; self.start() } }
}

let server = Server()
server.start()

// forward stop signals from launchd to the server
for sig in [SIGTERM, SIGINT, SIGHUP] {
    signal(sig, SIG_IGN)
    let src = DispatchSource.makeSignalSource(signal: sig, queue: .main)
    src.setEventHandler { server.intentional = true; kill(server.pid, sig); exit(0) }
    src.resume()
    _ = Unmanaged.passRetained(src as AnyObject)
}

// ---------------- helpers ----------------
func fetchTray() -> [String: Any]? {
    guard let url = URL(string: "http://127.0.0.1:\(port)/api/tray") else { return nil }
    var req = URLRequest(url: url); req.timeoutInterval = 1.5
    var result: [String: Any]?
    let sem = DispatchSemaphore(value: 0)
    URLSession.shared.dataTask(with: req) { data, _, _ in
        if let d = data { result = try? JSONSerialization.jsonObject(with: d) as? [String: Any] }
        sem.signal()
    }.resume()
    _ = sem.wait(timeout: .now() + 2)
    return result
}

@discardableResult func launchctl(_ args: [String]) -> String {
    let p = Process(); p.executableURL = URL(fileURLWithPath: "/bin/launchctl"); p.arguments = args
    let pipe = Pipe(); p.standardOutput = pipe; p.standardError = pipe
    try? p.run(); p.waitUntilExit()
    return String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
}

/// Autostart at login = the LaunchAgent is not disabled.
func autostartOn() -> Bool {
    let out = launchctl(["print-disabled", "gui/\(uid)"])
    for line in out.split(separator: "\n") where line.contains("\"\(LABEL)\"") {
        return !(line.contains("=> disabled") || line.contains("=> true"))
    }
    return true
}

func ago(_ s: Int) -> String {
    if s < 10 { return "сейчас" }
    if s < 60 { return "\(s) с назад" }
    return "\(s / 60) мин назад"
}

// ---------------- menu-bar icon ----------------
final class Tray: NSObject, NSMenuDelegate {
    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    let menu = NSMenu()
    var url = "http://localhost:\(port)"

    override init() {
        super.init()
        menu.delegate = self
        item.menu = menu
        setIcon(ok: true)
        Timer.scheduledTimer(withTimeInterval: 20, repeats: true) { [weak self] _ in
            DispatchQueue.global().async { let ok = fetchTray() != nil; DispatchQueue.main.async { self?.setIcon(ok: ok) } }
        }
    }

    func setIcon(ok: Bool) {
        let name = ok ? "ipad.landscape" : "exclamationmark.triangle"
        let img = NSImage(systemSymbolName: name, accessibilityDescription: "TabDock") ?? NSImage()
        img.isTemplate = true
        item.button?.image = img
        item.button?.toolTip = ok ? "TabDock работает" : "TabDock не отвечает"
    }

    private func add(_ title: String, _ action: Selector? = nil, key: String = "", enabled: Bool = true, indent: Int = 0) -> NSMenuItem {
        let mi = NSMenuItem(title: title, action: action, keyEquivalent: key)
        mi.target = self; mi.isEnabled = enabled && action != nil; mi.indentationLevel = indent
        menu.addItem(mi); return mi
    }

    // rebuilt every time the menu opens, so it is always current
    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        let t = fetchTray()
        setIcon(ok: t != nil)
        if let t = t {
            url = (t["url"] as? String).map { $0.components(separatedBy: "/?").first ?? $0 } ?? url
            _ = add("TabDock \(t["version"] as? String ?? "") — работает")
            _ = add("Адрес: \(url)  (скопировать)", #selector(copyAddress))
            if t["vpn"] as? Bool == true { _ = add("VPN включён — устройства дома подключаются напрямую") }
            if let v = t["update"] as? String { _ = add("Доступна версия \(v) — обновить…", #selector(openDock)) }
            menu.addItem(.separator())
            let clients = t["clients"] as? [[String: Any]] ?? []
            _ = add(clients.isEmpty ? "Подключённых устройств нет" : "Подключено устройств: \(clients.count)")
            for c in clients {
                let kind = (c["kind"] as? String) == "app" ? "" : " (браузер)"
                _ = add("\(c["name"] as? String ?? "?")\(kind) · \(c["ip"] as? String ?? "") · \(ago(c["ago"] as? Int ?? 0))", indent: 1)
            }
        } else {
            _ = add("TabDock не отвечает — перезапустите службу")
        }
        menu.addItem(.separator())
        _ = add("Передача файлов…", #selector(showTransfer), key: "t")
        _ = add("Показать QR-код для подключения…", #selector(showQR))
        _ = add("Открыть панель TabDock", #selector(openDock))
        menu.addItem(.separator())
        let auto = add("Запускать при входе", #selector(toggleAutostart))
        auto.state = autostartOn() ? .on : .off
        _ = add("Перезапустить службу", #selector(restart))
        _ = add("Открыть журнал", #selector(openLog))
        menu.addItem(.separator())
        _ = add("Остановить TabDock…", #selector(stopAll))
    }

    // «Передача файлов»: a small window with the drag-and-drop page of the local server
    var transferWindow: NSWindow?
    @objc func showTransfer() {
        if transferWindow == nil {
            let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 460, height: 620),
                             styleMask: [.titled, .closable, .resizable, .miniaturizable], backing: .buffered, defer: false)
            w.title = "TabDock — передача файлов"
            w.isReleasedWhenClosed = false
            let web = WKWebView(frame: w.contentView!.bounds)
            web.autoresizingMask = [.width, .height]
            w.contentView!.addSubview(web)
            web.load(URLRequest(url: URL(string: "http://localhost:\(port)/transfer")!))
            w.center()
            transferWindow = w
        }
        NSApp.activate(ignoringOtherApps: true)
        transferWindow?.makeKeyAndOrderFront(nil)
    }

    @objc func copyAddress() {
        NSPasteboard.general.clearContents(); NSPasteboard.general.setString(url, forType: .string)
    }
    // the control panel on this computer: QR code, devices, password, updates
    @objc func showQR() { NSWorkspace.shared.open(URL(string: "http://localhost:\(port)/")!) }
    @objc func openDock() { NSWorkspace.shared.open(URL(string: "http://localhost:\(port)/")!) }
    @objc func openLog() {
        let err = logDir.appendingPathComponent("tabdock.err.log")
        NSWorkspace.shared.open(FileManager.default.fileExists(atPath: err.path) ? err : logDir)
    }
    @objc func toggleAutostart() {
        launchctl([autostartOn() ? "disable" : "enable", "gui/\(uid)/\(LABEL)"])
    }
    @objc func restart() {
        setIcon(ok: false)
        server.restart()
        DispatchQueue.main.asyncAfter(deadline: .now() + 4) { [weak self] in self?.setIcon(ok: fetchTray() != nil) }
    }
    @objc func stopAll() {
        NSApp.activate(ignoringOtherApps: true)
        let a = NSAlert()
        a.messageText = "Остановить TabDock?"
        a.informativeText = "Планшеты и телефоны перестанут получать данные. " +
            (autostartOn() ? "TabDock снова запустится при следующем входе в систему." : "Автозапуск выключен — запустите TabDock вручную.")
        a.addButton(withTitle: "Остановить"); a.addButton(withTitle: "Отмена")
        guard a.runModal() == .alertFirstButtonReturn else { return }
        // a clean exit (code 0) is not restarted by launchd (KeepAlive: SuccessfulExit = false)
        server.stop { exit(0) }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)   // no Dock icon, only the menu bar
let tray = Tray()
app.run()
