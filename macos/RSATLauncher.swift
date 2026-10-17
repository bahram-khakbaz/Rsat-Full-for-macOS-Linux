import AppKit
import WebKit
import Foundation

class Launcher: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    var window: NSWindow!
    let status = NSTextField(labelWithString: "Starting Docker and RSAT…")
    let spinner = NSProgressIndicator()
    let retry = NSButton(title: "Retry", target: nil, action: nil)
    let logs = NSButton(title: "Open startup log", target: nil, action: nil)
    var web: WKWebView?
    var running = false
    var process: Process?
    var config: [String:String] = [:]
    var downloads: [ObjectIdentifier:(temporary:URL,destination:URL)] = [:]

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
        // An already-healthy installation needs no second Docker startup.
        var request = URLRequest(url:URL(string:"http://localhost:8080/api/health")!)
        request.timeoutInterval = 3
        URLSession.shared.dataTask(with:request) { data,response,_ in
            let info = data.flatMap { try? JSONSerialization.jsonObject(with:$0) as? [String:Any] }
            if (response as? HTTPURLResponse)?.statusCode == 200, info?["status"] as? String == "ok" {
                DispatchQueue.main.async { self.running = false; self.showPanel() }
            } else { DispatchQueue.main.async { self.startServices() } }
        }.resume()
    }

    func startServices() {
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
    @objc func reloadPanel() { web?.reload() }
    func showPanel() {
        spinner.stopAnimation(nil)
        status.isHidden = true; retry.isHidden = true; logs.isHidden = true
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        let browser = WKWebView(frame: window.contentView!.bounds, configuration: configuration)
        browser.autoresizingMask = [.width,.height]
        browser.navigationDelegate = self
        browser.uiDelegate = self
        window.contentView!.addSubview(browser); web = browser
        browser.load(URLRequest(url: URL(string: "http://localhost:8080/#users")!))
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        webView.removeFromSuperview(); web = nil; status.isHidden = false
        fail("The local panel could not load. Retry to check its services.")
    }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        guard ["localhost","127.0.0.1"].contains(frame.securityOrigin.host), frame.securityOrigin.port == 8080 else { completionHandler(nil); return }
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.canChooseFiles = !parameters.allowsDirectories
        panel.beginSheetModal(for:window) { result in completionHandler(result == .OK ? panel.urls : nil) }
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        decisionHandler(navigationAction.shouldPerformDownload ? .download : .allow)
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse,
                 decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        decisionHandler(navigationResponse.canShowMIMEType ? .allow : .download)
    }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse,
                  suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = (suggestedFilename as NSString).lastPathComponent
        panel.canCreateDirectories = true
        panel.beginSheetModal(for:window) { result in
            guard result == .OK, let target = panel.url else { completionHandler(nil); return }
            let temporary = target.deletingLastPathComponent().appendingPathComponent(".rsat-download-" + UUID().uuidString + ".part")
            self.downloads[ObjectIdentifier(download)] = (temporary,target)
            completionHandler(temporary)
        }
    }
    func downloadDidFinish(_ download: WKDownload) {
        guard let item = downloads.removeValue(forKey:ObjectIdentifier(download)) else { return }
        do {
            if FileManager.default.fileExists(atPath:item.destination.path) {
                _ = try FileManager.default.replaceItemAt(item.destination, withItemAt:item.temporary)
            } else { try FileManager.default.moveItem(at:item.temporary,to:item.destination) }
        } catch {
            let alert = NSAlert(); alert.messageText = "Could not save the downloaded file"
            alert.informativeText = "The received data remains in a .rsat-download temporary file beside the selected destination. Check folder permissions and available disk space."
            alert.beginSheetModal(for:window)
        }
    }
    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        if let item = downloads.removeValue(forKey:ObjectIdentifier(download)) { try? FileManager.default.removeItem(at:item.temporary) }
        if (error as NSError).code != NSURLErrorCancelled {
            let alert = NSAlert(); alert.messageText = "Download did not complete"
            alert.informativeText = "The destination was not replaced. Retry the transfer after checking the connection."
            alert.beginSheetModal(for:window)
        }
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationWillTerminate(_ notification: Notification) { process?.terminate() }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = Launcher()
let mainMenu = NSMenu(), appItem = NSMenuItem(), appMenu = NSMenu()
mainMenu.addItem(appItem); appItem.submenu = appMenu
appMenu.addItem(withTitle:"Reload Panel",action:#selector(Launcher.reloadPanel),keyEquivalent:"r").target = delegate
appMenu.addItem(withTitle:"Quit RSAT",action:#selector(NSApplication.terminate(_:)),keyEquivalent:"q")
let editItem = NSMenuItem(title:"Edit",action:nil,keyEquivalent:""), editMenu = NSMenu(title:"Edit")
for (title,action,key) in [("Cut",#selector(NSText.cut(_:)),"x"),("Copy",#selector(NSText.copy(_:)),"c"),("Paste",#selector(NSText.paste(_:)),"v"),("Select All",#selector(NSText.selectAll(_:)),"a")] { editMenu.addItem(withTitle:title,action:action,keyEquivalent:key) }
editItem.submenu = editMenu; mainMenu.addItem(editItem); app.mainMenu = mainMenu
app.delegate = delegate
app.run()
