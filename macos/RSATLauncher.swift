import AppKit
import WebKit
import Foundation

class Launcher: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    var window: NSWindow!
    let status = NSTextField(labelWithString: "Starting Docker and RSAT…")
    let spinner = NSProgressIndicator()
    let retry = NSButton(title: "Retry", target: nil, action: nil)
    let logs = NSButton(title: "Open startup log", target: nil, action: nil)
    var web: WKWebView?
    var running = false
    var process: Process?
    var config: [String:String] = [:]

    func applicationDidFinishLaunching(_ notification: Notification) {
        guard let path = Bundle.main.url(forResource: "launcher", withExtension: "json"),
              let data = try? Data(contentsOf: path),
              let parsed = try? JSONSerialization.jsonObject(with: data) as? [String:String] else {
            NSApp.terminate(nil); return
        }
        config = parsed
        window = NSWindow(contentRect: NSRect(x: 0,y: 0,width: 1200,height: 800), styleMask: [.titled,.closable,.miniaturizable,.resizable], backing: .buffered, defer: false)
        window.title = "RSAT"
        window.minSize = NSSize(width: 800,height: 600)
        window.center()
        let view = window.contentView!
        status.alignment = .center
        status.frame = NSRect(x: 80,y: 430,width: 1040,height: 60)
        status.autoresizingMask = [.width,.minYMargin,.maxYMargin]
        status.font = NSFont.systemFont(ofSize: 18)
        view.addSubview(status)
        spinner.style = .spinning
        spinner.frame = NSRect(x: 580,y: 390,width: 40,height: 40)
        spinner.autoresizingMask = [.minXMargin,.maxXMargin,.minYMargin,.maxYMargin]
        view.addSubview(spinner)
        retry.target = self; retry.action = #selector(start)
        retry.frame = NSRect(x: 500,y: 330,width: 85,height: 32)
        retry.autoresizingMask = [.minXMargin,.maxXMargin,.minYMargin,.maxYMargin]
        view.addSubview(retry)
        logs.target = self; logs.action = #selector(openLog)
        logs.frame = NSRect(x: 595,y: 330,width: 160,height: 32)
        logs.autoresizingMask = [.minXMargin,.maxXMargin,.minYMargin,.maxYMargin]
        view.addSubview(logs)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        start()
    }

    @objc func start() {
        if running { return }
        running = true; retry.isHidden = true; logs.isHidden = true
        status.stringValue = "Starting Docker and RSAT… This may take a minute after restarting your Mac."
        spinner.startAnimation(nil)
        guard let script = Bundle.main.path(forResource: "start-rsat", ofType: "sh"),
              let repo = config["repository"], let log = config["log"] else { fail("Launcher configuration is missing."); return }
        DispatchQueue.global(qos: .userInitiated).async {
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/bin/bash")
            task.arguments = [script, repo]
            try? FileManager.default.createDirectory(at: URL(fileURLWithPath: log).deletingLastPathComponent(), withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            FileManager.default.createFile(atPath: log, contents: Data(), attributes: [.posixPermissions: 0o600])
            guard let handle = FileHandle(forWritingAtPath: log) else {
                DispatchQueue.main.async { self.fail("Cannot create the startup log.") }; return
            }
            task.standardOutput = handle; task.standardError = handle
            DispatchQueue.main.async { self.process = task }
            do {
                try task.run(); task.waitUntilExit(); try? handle.close()
                DispatchQueue.main.async {
                    self.process = nil; self.running = false
                    if task.terminationStatus == 0 { self.showPanel() }
                    else { self.fail("RSAT could not start. Open the startup log and retry.") }
                }
            } catch {
                try? handle.close()
                DispatchQueue.main.async { self.fail("Unable to launch the installed RSAT services.") }
            }
        }
    }

    func fail(_ message: String) {
        running = false; spinner.stopAnimation(nil)
        status.stringValue = message; retry.isHidden = false; logs.isHidden = false
    }
    @objc func openLog() {
        if let path = config["log"] { NSWorkspace.shared.open(URL(fileURLWithPath: path)) }
    }
    func showPanel() {
        spinner.stopAnimation(nil)
        status.isHidden = true; retry.isHidden = true; logs.isHidden = true
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        let browser = WKWebView(frame: window.contentView!.bounds, configuration: configuration)
        browser.autoresizingMask = [.width,.height]
        browser.navigationDelegate = self
        window.contentView!.addSubview(browser); web = browser
        browser.load(URLRequest(url: URL(string: "http://localhost:8080/#users")!))
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        webView.removeFromSuperview(); web = nil; status.isHidden = false
        fail("The local panel could not load. Retry to check its services.")
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = Launcher()
app.delegate = delegate
app.run()
