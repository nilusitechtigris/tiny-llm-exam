// Render a local HTML file to a PNG with WebKit.
// usage: swift render_png.swift <in.html> <out.png> <width> <height>
import AppKit
import WebKit

let args = CommandLine.arguments
let inURL = URL(fileURLWithPath: args[1])
let outPath = args[2]
let w = CGFloat(Double(args[3]) ?? 1080), h = CGFloat(Double(args[4]) ?? 1350)

class Delegate: NSObject, WKNavigationDelegate {
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        // give web fonts a moment to load
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
            let cfg = WKSnapshotConfiguration()
            cfg.rect = CGRect(x: 0, y: 0, width: w, height: h)
            cfg.snapshotWidth = NSNumber(value: Double(w) * 2) // 2x for crisp text
            webView.takeSnapshot(with: cfg) { img, err in
                guard let img = img, let tiff = img.tiffRepresentation,
                      let rep = NSBitmapImageRep(data: tiff),
                      let png = rep.representation(using: .png, properties: [:]) else {
                    print("snapshot failed: \(String(describing: err))"); exit(1)
                }
                try! png.write(to: URL(fileURLWithPath: outPath))
                print("wrote \(outPath) \(rep.pixelsWide)x\(rep.pixelsHigh)")
                exit(0)
            }
        }
    }
}

let app = NSApplication.shared
let win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: w, height: h), styleMask: [.borderless], backing: .buffered, defer: false)
let web = WKWebView(frame: NSRect(x: 0, y: 0, width: w, height: h))
let del = Delegate()
web.navigationDelegate = del
win.contentView = web
web.loadFileURL(inURL, allowingReadAccessTo: inURL.deletingLastPathComponent())
DispatchQueue.main.asyncAfter(deadline: .now() + 30) { print("timeout"); exit(2) }
app.run()
